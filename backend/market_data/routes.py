"""Market Intelligence Layer APIs: watchlists, scanning, context, and AI bridge."""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from backend.ai_models.ai_decision_engine import AIDecisionEngine
from backend.db.ai_db import get_ai_execution_settings
from backend.market_data.market_data_service import MarketIntelligenceService, ProviderUnavailable
from backend.market_data.watchlists import (
    add_symbol,
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    list_watchlists,
    remove_symbol,
    rename_watchlist,
)
from backend.security.audit import record_audit_event


router = APIRouter(prefix='/market', tags=['market-intelligence'])
_market_intelligence = MarketIntelligenceService()
_ai_decision_engine = AIDecisionEngine()


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class WatchlistRequest(_StrictModel):
    name: str = Field(min_length=1, max_length=80)


class SymbolRequest(_StrictModel):
    symbol: str = Field(min_length=1, max_length=15, pattern=r'^[A-Za-z0-9.\-]+$')


class ScannerRequest(_StrictModel):
    symbols: List[str] = Field(default_factory=list, max_length=50)
    watchlist_id: Optional[str] = None


@router.get('/health')
def market_health() -> dict[str, Any]:
    return _market_intelligence.health()


@router.get('/providers')
def market_providers() -> dict[str, Any]:
    health = _market_intelligence.health()
    return {
        'providers': health['providers'],
        'paid_api_required': False,
        'premium_provider_supported_later': True,
        'paper_only': True,
    }


@router.get('/economic-calendar')
def economic_calendar(days: int = 14) -> dict[str, Any]:
    if not 1 <= days <= 90:
        raise HTTPException(status_code=422, detail='Days must be between 1 and 90')
    try:
        return _market_intelligence.get_economic_calendar(days=days)
    except ProviderUnavailable as error:
        raise HTTPException(status_code=503, detail='Economic calendar is temporarily unavailable') from error


@router.get('/context/{symbol}')
def market_context(symbol: str) -> dict[str, Any]:
    try:
        return _market_intelligence.get_market_context(symbol)
    except ValueError as error:
        raise HTTPException(status_code=422, detail='Symbol is invalid') from error
    except ProviderUnavailable as error:
        raise HTTPException(status_code=503, detail='Market context is temporarily unavailable') from error


@router.post('/scanner')
def scanner(request: ScannerRequest) -> dict[str, Any]:
    symbols = list(request.symbols)
    if request.watchlist_id:
        watchlist = get_watchlist(request.watchlist_id)
        if not watchlist:
            raise HTTPException(status_code=404, detail='Watchlist not found')
        symbols.extend(watchlist['symbols'])
    if not symbols:
        raise HTTPException(status_code=422, detail='Provide symbols or a watchlist with symbols to scan')
    try:
        return _market_intelligence.scan(symbols)
    except ValueError as error:
        raise HTTPException(status_code=422, detail='Scanner request is invalid') from error


@router.post('/ai-decisions/{symbol}', status_code=status.HTTP_201_CREATED)
def create_market_intelligence_decision(symbol: str) -> dict[str, Any]:
    """Feed collected no-key market context into the existing paper-only AI engine."""
    try:
        context = _market_intelligence.get_market_context(symbol)
        settings = get_ai_execution_settings()
        decision = _ai_decision_engine.create_decision(
            **context['ai_context'],
            execution_mode=settings['execution_mode'],
            model_key=settings['model_key'],
            decision_type='market_intelligence',
        )
        return {
            'decision': decision,
            'market_health': context['market_health'],
            'news_sentiment': context['news_sentiment'],
            'economic_calendar': context['economic_calendar'],
            'paper_only': True,
        }
    except ValueError as error:
        raise HTTPException(status_code=422, detail='Market intelligence decision request is invalid') from error
    except ProviderUnavailable as error:
        raise HTTPException(status_code=503, detail='Market intelligence is temporarily unavailable') from error


@router.get('/watchlists')
def get_watchlists() -> dict[str, Any]:
    watchlists = list_watchlists()
    return {'watchlists': watchlists, 'count': len(watchlists)}


@router.post('/watchlists', status_code=status.HTTP_201_CREATED)
def post_watchlist(request: WatchlistRequest, http_request: Request) -> dict[str, Any]:
    try:
        watchlist = create_watchlist(request.name)
        record_audit_event('settings_change', 'watchlist_created', 'watchlist', watchlist['id'], request=http_request)
        return watchlist
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.put('/watchlists/{watchlist_id}')
def put_watchlist(watchlist_id: str, request: WatchlistRequest, http_request: Request) -> dict[str, Any]:
    try:
        watchlist = rename_watchlist(watchlist_id, request.name)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not watchlist:
        raise HTTPException(status_code=404, detail='Watchlist not found')
    record_audit_event('settings_change', 'watchlist_renamed', 'watchlist', watchlist_id, request=http_request)
    return watchlist


@router.delete('/watchlists/{watchlist_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_watchlist(watchlist_id: str, request: Request) -> None:
    if not delete_watchlist(watchlist_id):
        raise HTTPException(status_code=404, detail='Watchlist not found')
    record_audit_event('settings_change', 'watchlist_deleted', 'watchlist', watchlist_id, request=request)


@router.post('/watchlists/{watchlist_id}/symbols')
def post_watchlist_symbol(watchlist_id: str, request: SymbolRequest, http_request: Request) -> dict[str, Any]:
    try:
        watchlist = add_symbol(watchlist_id, request.symbol)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not watchlist:
        raise HTTPException(status_code=404, detail='Watchlist not found')
    record_audit_event('settings_change', 'watchlist_symbol_added', 'watchlist', watchlist_id, request=http_request,
                       details={'symbol': request.symbol.upper()})
    return watchlist


@router.delete('/watchlists/{watchlist_id}/symbols/{symbol}')
def delete_watchlist_symbol(watchlist_id: str, symbol: str, request: Request) -> dict[str, Any]:
    try:
        watchlist = remove_symbol(watchlist_id, symbol)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not watchlist:
        raise HTTPException(status_code=404, detail='Watchlist not found')
    record_audit_event('settings_change', 'watchlist_symbol_removed', 'watchlist', watchlist_id, request=request,
                       details={'symbol': symbol.upper()})
    return watchlist
