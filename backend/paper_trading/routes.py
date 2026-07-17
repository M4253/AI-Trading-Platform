"""REST endpoints for paper trading."""
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, Literal
from backend.paper_trading.paper_engine import PaperTradingEngine
from backend.paper_trading.paper_db import (
    get_paper_orders, get_paper_positions, get_paper_portfolio,
    get_paper_trading_state
)
from backend.security.audit import record_audit_event

router = APIRouter(prefix='/paper', tags=['paper-trading'])

# Global engine
_engine = PaperTradingEngine()


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PaperTradeRequest(_StrictModel):
    symbol: str = Field(min_length=1, max_length=15, pattern=r'^[A-Za-z0-9.\-]+$')
    qty: float = Field(gt=0, le=1_000_000)
    side: Literal['buy', 'sell']
    market_data: Dict[str, Any] = Field(default_factory=dict)
    market_regime: str = Field(default='neutral', min_length=1, max_length=32)


@router.post('/start')
def start_trading(request: Request):
    """Start paper trading."""
    _engine.start_trading()
    record_audit_event('trading_control', 'paper_trading_started', 'paper_engine', request=request)
    return {'status': 'started'}


@router.post('/pause')
def pause_trading(request: Request):
    """Pause paper trading."""
    _engine.pause_trading()
    record_audit_event('trading_control', 'paper_trading_paused', 'paper_engine', request=request)
    return {'status': 'paused'}


@router.post('/resume')
def resume_trading(request: Request):
    """Resume paper trading."""
    _engine.resume_trading()
    record_audit_event('trading_control', 'paper_trading_resumed', 'paper_engine', request=request)
    return {'status': 'resumed'}


@router.post('/stop-all')
def stop_all_trading(request: Request):
    """Emergency stop all trading."""
    _engine.stop_all_trading()
    record_audit_event('emergency_stop', 'all_new_orders_blocked', 'paper_engine', request=request)
    return {'status': 'halted', 'message': 'All new orders blocked'}


@router.get('/account')
def get_account():
    """Get paper account summary."""
    portfolio = get_paper_portfolio()
    status = get_paper_trading_state('status') or 'unknown'
    halted = get_paper_trading_state('trading_halted') == 'true'
    return {
        'portfolio': portfolio,
        'status': status,
        'trading_halted': halted
    }


@router.get('/positions')
def get_positions():
    """Get current positions."""
    positions = get_paper_positions()
    return {'positions': positions}


@router.get('/orders')
def get_orders(limit: int = 50):
    """Get orders."""
    orders = get_paper_orders(limit=max(1, min(limit, 200)))
    return {'orders': orders}


@router.post('/trade')
def execute_trade(req: PaperTradeRequest, request: Request):
    """Execute a paper trade."""
    portfolio = get_paper_portfolio()
    result = _engine.execute_trade(
        req.symbol, req.qty, req.side,
        req.market_data, 
        {'total_equity': portfolio.get('total_equity', 100000)},
        req.market_regime
    )
    record_audit_event(
        'trade_execution',
        'paper_order_executed' if result.get('executed') else 'trade_rejected',
        'paper_trade',
        (result.get('order') or {}).get('id'),
        request=request,
        details={'symbol': req.symbol.upper(), 'side': req.side, 'rejected': bool(result.get('rejected'))},
    )
    return result


@router.post('/orders/{order_id}/cancel')
def cancel_order(order_id: str, request: Request):
    """Cancel an order."""
    success = _engine.broker.cancel_order(order_id)
    if success:
        record_audit_event('trade_control', 'order_cancelled', 'paper_order', order_id, request=request)
        return {'status': 'cancelled'}
    record_audit_event('trade_control', 'cancellation_rejected', 'paper_order', order_id, request=request)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Order not found')
