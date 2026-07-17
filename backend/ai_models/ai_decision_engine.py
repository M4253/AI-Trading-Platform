"""A modular, auditable AI decision engine with paper-only execution.

This module intentionally contains no broker client, network call, or API-key
handling.  Models receive supplied market/chart/news context and can only send
an approved order through the existing guarded :class:`PaperTradingEngine`.
Future model providers implement ``DecisionModel`` and are registered here;
they do not need to change the persistence or execution policy layer.
"""
from __future__ import annotations

import math
import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence

from backend.db.ai_db import (
    get_ai_decision,
    insert_ai_audit_log,
    insert_ai_decision,
    insert_ai_decision_input,
    update_ai_decision_execution,
)
from backend.paper_trading.paper_db import get_paper_portfolio, get_paper_positions
from backend.paper_trading.paper_engine import PaperTradingEngine


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _finite_numbers(values: Any) -> List[float]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, Mapping)):
        return []
    return [_number(value) for value in values if math.isfinite(_number(value, math.nan))]


def _mean(values: Sequence[float]) -> Optional[float]:
    return statistics.fmean(values) if values else None


def _score_news_item(item: Any) -> Optional[float]:
    """Return a bounded -1..1 sentiment score without an external NLP service."""
    if isinstance(item, Mapping):
        for key in ('score', 'sentiment_score', 'sentiment'):
            value = item.get(key)
            if isinstance(value, (int, float)):
                score = _number(value)
                # Common feeds use 0..1 while others use -1..1.
                return _clamp(score * 2 - 1 if 0 <= score <= 1 else score, -1.0, 1.0)
        text = ' '.join(str(item.get(key, '')) for key in ('headline', 'title', 'summary')).lower()
    else:
        text = str(item).lower()
    if not text.strip():
        return None
    positive = ('beat', 'growth', 'upgrade', 'profit', 'bullish', 'surge', 'record', 'approval')
    negative = ('miss', 'downgrade', 'loss', 'bearish', 'lawsuit', 'cut', 'decline', 'risk')
    positive_hits = sum(word in text for word in positive)
    negative_hits = sum(word in text for word in negative)
    if positive_hits == negative_hits:
        return 0.0
    return _clamp((positive_hits - negative_hits) / 2.0, -1.0, 1.0)


def _derive_chart_features(chart_data: Optional[Mapping[str, Any]], market_data: Mapping[str, Any]) -> Dict[str, Any]:
    """Derive lightweight SMA, momentum, and RSI features from supplied candles."""
    chart_data = chart_data or {}
    closes = _finite_numbers(
        chart_data.get('closes')
        or chart_data.get('close')
        or chart_data.get('prices')
        or market_data.get('closes')
        or market_data.get('price_history')
    )
    current_close = _number(market_data.get('close'), 0.0)
    if not closes and current_close > 0:
        closes = [current_close]

    short_window = closes[-5:]
    long_window = closes[-20:]
    short_sma = _mean(short_window)
    long_sma = _mean(long_window)
    momentum = 0.0
    if len(closes) >= 2 and closes[0] > 0:
        momentum = _clamp((closes[-1] / closes[0] - 1.0) * 5.0, -1.0, 1.0)
    sma_signal = 0.0
    if short_sma and long_sma and long_sma > 0:
        sma_signal = _clamp((short_sma / long_sma - 1.0) * 20.0, -1.0, 1.0)

    rsi = None
    if len(closes) >= 3:
        changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
        average_gain = _mean([max(change, 0.0) for change in changes]) or 0.0
        average_loss = _mean([max(-change, 0.0) for change in changes]) or 0.0
        if average_loss == 0:
            rsi = 100.0 if average_gain else 50.0
        else:
            relative_strength = average_gain / average_loss
            rsi = 100.0 - (100.0 / (1.0 + relative_strength))

    return {
        'close_count': len(closes),
        'short_sma': round(short_sma, 4) if short_sma is not None else None,
        'long_sma': round(long_sma, 4) if long_sma is not None else None,
        'momentum_signal': round(momentum, 4),
        'sma_signal': round(sma_signal, 4),
        'derived_rsi': round(rsi, 2) if rsi is not None else None,
    }


@dataclass(frozen=True)
class ModelAssessment:
    action: str
    side: Optional[str]
    qty: float
    opportunity_score: float
    confidence_score: float
    risk_score: float
    expected_reward: Optional[float]
    risk_reward_ratio: Optional[float]
    reasoning: List[str]


class DecisionModel(Protocol):
    """Interface for an offline or future provider-backed decision model."""

    key: str
    display_name: str
    version: str

    def evaluate(self, context: Mapping[str, Any], features: Mapping[str, Any]) -> ModelAssessment:
        """Evaluate normalized context without executing a trade."""


class RuleBasedPaperModel:
    """Deterministic baseline model used until another registered model is selected."""

    key = 'rule_based_v1'
    display_name = 'Rule-based paper model'
    version = '1.0'

    def evaluate(self, context: Mapping[str, Any], features: Mapping[str, Any]) -> ModelAssessment:
        chart_signal = _number(features.get('chart_signal'))
        indicator_signal = _number(features.get('indicator_signal'))
        news_signal = _number(features.get('news_signal'))
        market_signal = _number(features.get('market_signal'))
        economic_signal = _number(features.get('economic_signal'))
        economic_risk = _number(features.get('economic_risk'))
        source_count = int(features.get('source_count', 0))
        volatility = _number(features.get('volatility'))
        price = _number(context.get('current_price'))
        portfolio = context.get('portfolio_state') or {}
        cash = _number(portfolio.get('current_cash', portfolio.get('cash', 0.0)))
        equity = _number(portfolio.get('total_equity', cash), max(cash, 1.0))
        current_position = _number(features.get('current_position_qty'))

        signal = _clamp(
            chart_signal * 0.35 + indicator_signal * 0.25 + news_signal * 0.20
            + market_signal * 0.10 + economic_signal * 0.10,
            -1.0,
            1.0,
        )
        strength = abs(signal)
        confidence = _clamp(32.0 + source_count * 11.0 + strength * 25.0, 0.0, 100.0)
        portfolio_exposure = _clamp(abs(current_position * price) / max(equity, 1.0), 0.0, 1.0)
        risk = _clamp(
            volatility * 100.0 * 2.0 + portfolio_exposure * 35.0
            + economic_risk * 100.0 + (100.0 - confidence) * 0.18,
            0.0,
            100.0,
        )
        opportunity = _clamp(50.0 + signal * 50.0, 0.0, 100.0)

        if signal >= 0.18 and confidence >= 55.0 and price > 0 and cash >= price:
            action, side = 'BUY', 'buy'
            budget = min(cash * 0.02, equity * 0.02)
            qty = float(max(1, min(10, int(budget / price) or 1)))
        elif signal <= -0.18 and confidence >= 55.0 and current_position > 0:
            action, side = 'SELL', 'sell'
            qty = float(max(1, min(current_position, max(1, int(current_position * 0.25)))))
        else:
            action, side, qty = 'HOLD', None, 0.0

        reasoning = [
            f"Model {self.key} combined supplied chart, indicator, news, and market signals into {signal:+.2f}.",
            f"Chart signal {chart_signal:+.2f}; indicator signal {indicator_signal:+.2f}; news signal {news_signal:+.2f}; market signal {market_signal:+.2f}; economic signal {economic_signal:+.2f}.",
            f"Confidence is {confidence:.1f}% from {source_count} available data source(s); estimated risk is {risk:.1f}%.",
        ]
        if action == 'BUY':
            reasoning.append(f"Paper BUY candidate: {qty:g} share(s), capped at 2% of paper equity.")
        elif action == 'SELL':
            reasoning.append(f"Paper SELL candidate: {qty:g} share(s), limited to the existing paper position.")
        else:
            reasoning.append('HOLD: the available paper-only evidence does not clear the trade threshold.')

        expected_reward = price * qty * 0.03 if qty else None
        expected_risk = price * qty * max(0.01, volatility) if qty else None
        return ModelAssessment(
            action=action,
            side=side,
            qty=qty,
            opportunity_score=round(opportunity, 2),
            confidence_score=round(confidence, 2),
            risk_score=round(risk, 2),
            expected_reward=round(expected_reward, 2) if expected_reward is not None else None,
            risk_reward_ratio=round(expected_reward / expected_risk, 2) if expected_risk else None,
            reasoning=reasoning,
        )


MODEL_REGISTRY: Dict[str, DecisionModel] = {
    RuleBasedPaperModel.key: RuleBasedPaperModel(),
}


def available_models() -> List[Dict[str, str]]:
    """Return selectable local model metadata; no provider credentials are exposed."""
    return [
        {'key': model.key, 'display_name': model.display_name, 'version': model.version}
        for model in MODEL_REGISTRY.values()
    ]


class AIDecisionEngine:
    """Coordinates context analysis, audit persistence, and guarded paper execution."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        model_registry: Optional[Mapping[str, DecisionModel]] = None,
    ) -> None:
        self.db_path = db_path
        self.model_registry = dict(model_registry or MODEL_REGISTRY)

    def _model(self, model_key: str) -> DecisionModel:
        model = self.model_registry.get(model_key)
        if not model:
            raise ValueError(f'Unknown AI model: {model_key}')
        return model

    def _features(
        self,
        *,
        symbol: str,
        current_price: float,
        market_data: Optional[Mapping[str, Any]],
        chart_data: Optional[Mapping[str, Any]],
        indicators: Optional[Mapping[str, Any]],
        news: Optional[Sequence[Any]],
        portfolio_state: Optional[Mapping[str, Any]],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        market = dict(market_data or {})
        charts = _derive_chart_features(chart_data, market)
        supplied_indicators = dict(indicators or {})
        rsi = _number(supplied_indicators.get('rsi', charts.get('derived_rsi', 50.0)), 50.0)
        macd = _number(supplied_indicators.get('macd', supplied_indicators.get('macd_histogram', 0.0)))
        trend_hint = _number(supplied_indicators.get('trend_score', 0.0))
        indicator_signal = _clamp(((rsi - 50.0) / 50.0) * 0.55 + math.tanh(macd * 10.0) * 0.30 + trend_hint * 0.15, -1.0, 1.0)
        chart_signal = _clamp((charts['momentum_signal'] + charts['sma_signal']) / 2.0, -1.0, 1.0)
        opening_price = _number(market.get('open'), current_price)
        market_signal = _clamp((current_price / opening_price - 1.0) * 15.0, -1.0, 1.0) if opening_price else 0.0
        news_scores = [score for score in (_score_news_item(item) for item in (news or [])) if score is not None]
        news_signal = _mean(news_scores) or 0.0
        economic_signal = _clamp(_number(market.get('economic_signal')), -1.0, 1.0)
        economic_risk = _clamp(_number(market.get('economic_risk')), 0.0, 1.0)
        positions = list((portfolio_state or {}).get('positions') or [])
        current_position = next(
            (_number(position.get('qty')) for position in positions if position.get('symbol') == symbol),
            0.0,
        )
        volatility = _number(market.get('volatility', supplied_indicators.get('volatility', 0.02)), 0.02)
        if volatility > 1:
            volatility /= 100.0

        source_count = sum([
            bool(market),
            charts['close_count'] >= 2,
            bool(supplied_indicators),
            bool(news_scores),
            bool(market.get('economic_events')),
            bool(portfolio_state),
        ])
        features = {
            'chart_signal': round(chart_signal, 4),
            'indicator_signal': round(indicator_signal, 4),
            'news_signal': round(news_signal, 4),
            'market_signal': round(market_signal, 4),
            'economic_signal': round(economic_signal, 4),
            'economic_risk': round(economic_risk, 4),
            'volatility': round(_clamp(volatility, 0.0, 1.0), 4),
            'source_count': source_count,
            'current_position_qty': current_position,
            'technical_indicators': {
                **charts,
                'rsi': round(rsi, 2),
                'macd': round(macd, 4),
            },
            'news_items_analyzed': len(news_scores),
        }
        context = {
            'symbol': symbol,
            'current_price': current_price,
            'market_data': market,
            'chart_data': dict(chart_data or {}),
            'indicators': supplied_indicators,
            'news': list(news or []),
            'portfolio_state': dict(portfolio_state or {}),
            'derived_features': features,
            'analyzed_at': _now(),
        }
        return context, features

    def create_decision(
        self,
        *,
        symbol: str,
        current_price: float,
        market_data: Optional[Mapping[str, Any]] = None,
        chart_data: Optional[Mapping[str, Any]] = None,
        indicators: Optional[Mapping[str, Any]] = None,
        news: Optional[Sequence[Any]] = None,
        portfolio_state: Optional[Mapping[str, Any]] = None,
        execution_mode: str = 'manual_approval',
        model_key: str = 'rule_based_v1',
        decision_type: str = 'trade',
    ) -> Dict[str, Any]:
        """Analyze supplied context, persist it, and optionally paper-execute it.

        ``automatic_paper`` is the only automatic option.  It remains subject
        to the paper engine's start/stop and risk checks.
        """
        if execution_mode not in {'manual_approval', 'automatic_paper'}:
            raise ValueError('Only manual_approval or automatic_paper execution modes are supported')
        normalized_symbol = symbol.strip().upper()
        price = _number(current_price)
        if not normalized_symbol or price <= 0:
            raise ValueError('A symbol and a positive current price are required')

        model = self._model(model_key)
        if portfolio_state is None:
            portfolio_state = {
                **(get_paper_portfolio(self.db_path) or {}),
                'positions': get_paper_positions(self.db_path),
            }
        context, features = self._features(
            symbol=normalized_symbol,
            current_price=price,
            market_data=market_data,
            chart_data=chart_data,
            indicators=indicators,
            news=news,
            portfolio_state=portfolio_state,
        )
        assessment = model.evaluate(context, features)
        decision_id = str(uuid.uuid4())
        if assessment.action == 'HOLD':
            decision_status, execution_status, outcome = 'held', 'not_requested', 'hold_no_execution'
        else:
            decision_status, execution_status = 'awaiting_approval', 'pending_approval'
            outcome = 'automatic_paper_requested' if execution_mode == 'automatic_paper' else 'manual_approval_required'

        decision = {
            'id': decision_id,
            'timestamp': _now(),
            'symbol': normalized_symbol,
            'proposed_action': assessment.action,
            'proposed_side': assessment.side,
            'proposed_qty': assessment.qty,
            'confidence_score': assessment.confidence_score,
            'opportunity_score': assessment.opportunity_score,
            'risk_score': assessment.risk_score,
            'expected_reward': assessment.expected_reward,
            'risk_reward_ratio': assessment.risk_reward_ratio,
            'rationale': '\n'.join(assessment.reasoning),
            'reasoning': assessment.reasoning,
            'inputs': {
                'market_data': market_data or {},
                'chart_data': chart_data or {},
                'indicators': indicators or {},
                'news': list(news or []),
                'portfolio_state': portfolio_state,
            },
            'context': context,
            'model_name': model.display_name,
            'model_version': model.version,
            'prompt_version': 'phase9-context-v1',
            'model_key': model.key,
            'decision_type': decision_type,
            'execution_mode': execution_mode,
            'decision_status': decision_status,
            'execution_status': execution_status,
            'outcome': outcome,
        }
        insert_ai_decision(decision, self.db_path)
        for input_name, input_value in decision['inputs'].items():
            insert_ai_decision_input(decision_id, input_name, input_value, db_path=self.db_path)
        insert_ai_audit_log(
            decision_id,
            'context_analysis',
            True,
            f'{model.key} analyzed chart, indicators, news, market data, and paper portfolio state.',
            self.db_path,
        )
        if assessment.action == 'HOLD':
            insert_ai_audit_log(decision_id, 'execution_policy', True, 'Hold decision requires no execution.', self.db_path)
        elif execution_mode == 'manual_approval':
            insert_ai_audit_log(decision_id, 'execution_policy', True, 'Manual approval is required before paper execution.', self.db_path)
        else:
            insert_ai_audit_log(decision_id, 'execution_policy', True, 'Automatic paper execution requested.', self.db_path)
            self.execute_saved_decision(decision_id, initiated_by='automatic_paper')

        return get_ai_decision(decision_id, self.db_path) or decision

    def execute_saved_decision(self, decision_id: str, *, initiated_by: str = 'manual_approval') -> Dict[str, Any]:
        """Execute only a persisted buy/sell decision through the paper engine."""
        decision = get_ai_decision(decision_id, self.db_path)
        if not decision:
            raise KeyError('AI decision not found')
        if decision.get('proposed_side') not in {'buy', 'sell'} or _number(decision.get('proposed_qty')) <= 0:
            raise ValueError('Hold decisions cannot be executed')
        if decision.get('execution_status') not in {'pending_approval', 'pending'}:
            raise ValueError('This decision has already reached an execution outcome')

        context = decision.get('context') or {}
        price = _number(context.get('current_price'))
        if price <= 0:
            raise ValueError('Saved decision has no valid paper price')
        signal = {
            'symbol': decision['symbol'],
            'qty': _number(decision['proposed_qty']),
            'side': decision['proposed_side'],
            'price': price,
            'market_regime': (context.get('market_data') or {}).get('market_regime', 'neutral'),
        }
        execution = decide_and_execute(signal, db_path=self.db_path)
        order_id = (execution.get('order') or {}).get('id')
        if execution.get('executed') and order_id:
            update_ai_decision_execution(
                decision_id,
                decision_status='approved',
                execution_status='paper_executed',
                outcome='paper_executed',
                execution_details=execution,
                order_id=order_id,
                db_path=self.db_path,
            )
            insert_ai_audit_log(decision_id, 'paper_execution', True, f'Paper order {order_id} executed via {initiated_by}.', self.db_path)
        else:
            reason = execution.get('reason', 'Paper engine rejected the decision')
            update_ai_decision_execution(
                decision_id,
                decision_status='paper_rejected',
                execution_status='paper_rejected',
                outcome='paper_execution_rejected',
                execution_details=execution,
                db_path=self.db_path,
            )
            insert_ai_audit_log(decision_id, 'paper_execution', False, reason, self.db_path)
        return get_ai_decision(decision_id, self.db_path) or decision

    def reject_saved_decision(self, decision_id: str, reason: str = 'Rejected by user') -> Dict[str, Any]:
        decision = get_ai_decision(decision_id, self.db_path)
        if not decision:
            raise KeyError('AI decision not found')
        if decision.get('execution_status') not in {'pending_approval', 'pending'}:
            raise ValueError('Only pending decisions can be rejected')
        update_ai_decision_execution(
            decision_id,
            decision_status='rejected_by_user',
            execution_status='not_executed',
            outcome='manual_rejection',
            execution_details={'reason': reason},
            db_path=self.db_path,
        )
        insert_ai_audit_log(decision_id, 'manual_review', True, reason, self.db_path)
        return get_ai_decision(decision_id, self.db_path) or decision


def decide_and_execute(signal: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
    """Submit an approved signal to the guarded paper engine and nothing else."""
    engine = PaperTradingEngine(db_path=db_path)
    symbol = signal.get('symbol')
    qty = _number(signal.get('qty'))
    side = signal.get('side')
    price = _number(signal.get('price') or signal.get('current_price') or 100.0, 100.0)
    portfolio = get_paper_portfolio(db_path=engine.db_path) or {}
    return engine.execute_trade(
        symbol=symbol,
        qty=qty,
        side=side,
        market_data={'close': price},
        portfolio_state={'total_equity': portfolio.get('total_equity', 0.0)},
        market_regime=signal.get('market_regime', 'neutral'),
    )
