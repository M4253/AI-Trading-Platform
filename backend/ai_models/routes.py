"""REST API for the Phase 9 paper-only AI decision engine."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from backend.ai_models.ai_decision_engine import AIDecisionEngine, available_models
from backend.db.ai_db import (
    get_ai_decision,
    get_ai_execution_settings,
    list_ai_decision_audit,
    list_ai_decisions,
    update_ai_execution_settings,
)
from backend.paper_trading.paper_db import get_paper_portfolio, get_paper_positions
from backend.security.audit import record_audit_event


router = APIRouter(prefix='/ai', tags=['ai-decision-engine'])
_decision_engine = AIDecisionEngine()
_SENSITIVE_CONTEXT_KEYS = {
    'api_key', 'apikey', 'api_secret', 'password', 'passphrase',
    'access_token', 'refresh_token', 'broker_token', 'account_number',
}


class _StrictModel(BaseModel):
    """Do not silently accept credential or broker fields in AI API payloads."""

    model_config = ConfigDict(extra='forbid')


class AIContextRequest(_StrictModel):
    symbol: str = Field(min_length=1, max_length=16)
    current_price: float = Field(gt=0)
    market_data: Dict[str, Any] = Field(default_factory=dict)
    chart_data: Dict[str, Any] = Field(default_factory=dict)
    indicators: Dict[str, Any] = Field(default_factory=dict)
    news: List[Dict[str, Any]] = Field(default_factory=list)
    market_regime: str = Field(default='neutral', max_length=32)
    # Legacy analysis inputs are retained as local context only.  They are not
    # fetched from any provider and do not use external credentials.
    fundamentals: Optional[Dict[str, Any]] = None
    sentiment: Optional[Dict[str, Any]] = None
    macro_data: Optional[Dict[str, Any]] = None


class AITradeProposalRequest(AIContextRequest):
    # Retained for API compatibility. Execution policy always comes from saved
    # settings, so a request cannot force automatic execution or order sizing.
    auto_execute: bool = False
    proposed_qty: Optional[float] = Field(default=None, gt=0)


class AISettingsUpdateRequest(_StrictModel):
    execution_mode: Optional[Literal['manual_approval', 'automatic_paper']] = None
    model_key: Optional[str] = Field(default=None, min_length=1, max_length=80)


class DecisionRejectionRequest(_StrictModel):
    reason: str = Field(default='Rejected by user', min_length=1, max_length=500)


class LegacyExecutionRequest(_StrictModel):
    decision_id: str = Field(min_length=1)


def _paper_portfolio_state() -> Dict[str, Any]:
    """Use only the local paper portfolio; a client cannot supply account state."""
    return {
        **(get_paper_portfolio() or {}),
        'positions': get_paper_positions(),
    }


def _assert_credential_free(value: Any) -> None:
    """Reject credentials even when they are nested in an unstructured context."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower().replace('-', '_') in _SENSITIVE_CONTEXT_KEYS:
                raise ValueError('AI decision context cannot contain credentials or account identifiers')
            _assert_credential_free(child)
    elif isinstance(value, list):
        for child in value:
            _assert_credential_free(child)


def _request_context(request: AIContextRequest) -> Dict[str, Any]:
    indicators = dict(request.indicators)
    if request.fundamentals:
        indicators['fundamentals'] = request.fundamentals
    if request.macro_data:
        indicators['macro_data'] = request.macro_data
    news = list(request.news)
    if request.sentiment:
        news.append(request.sentiment)
    market_data = {**request.market_data, 'market_regime': request.market_regime}
    _assert_credential_free({
        'market_data': market_data,
        'chart_data': request.chart_data,
        'indicators': indicators,
        'news': news,
    })
    return {
        'symbol': request.symbol,
        'current_price': request.current_price,
        'market_data': market_data,
        'chart_data': request.chart_data,
        'indicators': indicators,
        'news': news,
        'portfolio_state': _paper_portfolio_state(),
    }


def _create_decision(
    request: AIContextRequest,
    *, execution_mode: str,
    model_key: str,
    decision_type: str,
) -> Dict[str, Any]:
    return _decision_engine.create_decision(
        **_request_context(request),
        execution_mode=execution_mode,
        model_key=model_key,
        decision_type=decision_type,
    )


@router.get('/settings')
def get_settings() -> Dict[str, Any]:
    """Return safe local policy.  Live execution is not an available setting."""
    return get_ai_execution_settings()


@router.patch('/settings')
def update_settings(request: AISettingsUpdateRequest, http_request: Request) -> Dict[str, Any]:
    if request.model_key and request.model_key not in {model['key'] for model in available_models()}:
        raise HTTPException(status_code=422, detail='Selected AI model is not registered')
    try:
        updated = update_ai_execution_settings(
            execution_mode=request.execution_mode,
            model_key=request.model_key,
        )
        record_audit_event(
            'settings_change', 'ai_execution_settings_updated', 'ai_execution_settings',
            request=http_request,
            details={'execution_mode': updated['execution_mode'], 'model_key': updated['model_key']},
        )
        return updated
    except ValueError as error:
        raise HTTPException(status_code=422, detail='AI execution settings are invalid') from error


@router.get('/models')
def list_models() -> Dict[str, Any]:
    return {
        'models': available_models(),
        'external_provider_connected': False,
        'paper_only': True,
    }


@router.post('/decisions', status_code=status.HTTP_201_CREATED)
def create_decision(request: AIContextRequest) -> Dict[str, Any]:
    """Analyze context and follow the saved manual/automatic-paper policy."""
    settings = get_ai_execution_settings()
    try:
        return _create_decision(
            request,
            execution_mode=settings['execution_mode'],
            model_key=settings['model_key'],
            decision_type='trade',
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail='AI decision context is invalid') from error


@router.post('/decisions/{decision_id}/approve')
def approve_decision(decision_id: str, request: Request) -> Dict[str, Any]:
    """Manually approve one persisted decision for guarded paper execution."""
    try:
        decision = _decision_engine.execute_saved_decision(decision_id, initiated_by='manual_approval')
        record_audit_event(
            'decision_approval',
            'paper_execution_approved' if decision['execution_status'] == 'paper_executed' else 'paper_execution_rejected',
            'ai_decision', decision_id, request=request,
            details={'execution_status': decision['execution_status'], 'paper_only': True},
        )
        return decision
    except KeyError as error:
        raise HTTPException(status_code=404, detail='AI decision not found') from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail='AI decision cannot be approved in its current state') from error


@router.post('/decisions/{decision_id}/reject')
def reject_decision(decision_id: str, request: DecisionRejectionRequest, http_request: Request) -> Dict[str, Any]:
    try:
        decision = _decision_engine.reject_saved_decision(decision_id, request.reason)
        record_audit_event(
            'decision_approval', 'decision_rejected', 'ai_decision', decision_id,
            request=http_request, details={'execution_status': decision['execution_status']},
        )
        return decision
    except KeyError as error:
        raise HTTPException(status_code=404, detail='AI decision not found') from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail='AI decision cannot be rejected in its current state') from error


@router.post('/analyze')
def analyze_opportunity(request: AIContextRequest) -> Dict[str, Any]:
    """Compatibility endpoint that records a non-executing analysis decision."""
    try:
        decision = _create_decision(
            request,
            execution_mode='manual_approval',
            model_key=get_ai_execution_settings()['model_key'],
            decision_type='analysis',
        )
        return {
            'decision_id': decision['id'],
            'symbol': decision['symbol'],
            'action': decision['proposed_action'],
            'opportunity_score': decision['opportunity_score'],
            'confidence_score': decision['confidence_score'],
            'risk_score': decision['risk_score'],
            'rationale': decision['rationale'],
            'reasoning': decision['reasoning'],
            'paper_only': True,
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail='AI analysis context is invalid') from error


@router.post('/propose-trade')
def propose_trade(request: AITradeProposalRequest) -> Dict[str, Any]:
    """Compatibility endpoint. Request-level auto execution is intentionally ignored."""
    settings = get_ai_execution_settings()
    try:
        decision = _create_decision(
            request,
            execution_mode=settings['execution_mode'],
            model_key=settings['model_key'],
            decision_type='trade',
        )
        proposal = decision if decision['proposed_action'] != 'HOLD' else None
        return {
            'proposal': proposal,
            'decision': decision,
            'awaiting_approval': decision['execution_status'] == 'pending_approval',
            'reason': 'Thresholds not met' if proposal is None else None,
            'request_auto_execute_ignored': request.auto_execute,
            'execution_mode': settings['execution_mode'],
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail='AI trade proposal context is invalid') from error


@router.post('/execute-proposal')
def execute_proposal(request: LegacyExecutionRequest, http_request: Request) -> Dict[str, Any]:
    """Legacy alias that now requires a saved decision id, never a raw order."""
    return approve_decision(request.decision_id, http_request)


@router.get('/decisions')
def list_decisions(limit: int = 50) -> Dict[str, Any]:
    decisions = list_ai_decisions(limit=limit)
    return {'decisions': decisions, 'count': len(decisions), 'paper_only': True}


@router.get('/decisions/{decision_id}')
def get_decision(decision_id: str) -> Dict[str, Any]:
    decision = get_ai_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail='AI decision not found')
    decision['audit_trail'] = list_ai_decision_audit(decision_id)
    return decision
