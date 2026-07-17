"""REST endpoints for paper trading."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from backend.paper_trading.paper_engine import PaperTradingEngine
from backend.paper_trading.paper_db import (
    get_paper_orders, get_paper_positions, get_paper_portfolio,
    get_paper_trading_state
)

router = APIRouter(prefix='/paper', tags=['paper-trading'])

# Global engine
_engine = PaperTradingEngine()


class PaperTradeRequest(BaseModel):
    symbol: str
    qty: float
    side: str
    market_data: Dict = {}
    market_regime: str = 'neutral'


class PaperOrderCancelRequest(BaseModel):
    order_id: str


@router.post('/start')
def start_trading():
    """Start paper trading."""
    _engine.start_trading()
    return {'status': 'started'}


@router.post('/pause')
def pause_trading():
    """Pause paper trading."""
    _engine.pause_trading()
    return {'status': 'paused'}


@router.post('/resume')
def resume_trading():
    """Resume paper trading."""
    _engine.resume_trading()
    return {'status': 'resumed'}


@router.post('/stop-all')
def stop_all_trading():
    """Emergency stop all trading."""
    _engine.stop_all_trading()
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
    orders = get_paper_orders(limit=limit)
    return {'orders': orders}


@router.post('/trade')
def execute_trade(req: PaperTradeRequest):
    """Execute a paper trade."""
    portfolio = get_paper_portfolio()
    result = _engine.execute_trade(
        req.symbol, req.qty, req.side,
        req.market_data, 
        {'total_equity': portfolio.get('total_equity', 100000)},
        req.market_regime
    )
    return result


@router.post('/orders/{order_id}/cancel')
def cancel_order(order_id: str):
    """Cancel an order."""
    success = _engine.broker.cancel_order(order_id)
    if success:
        return {'status': 'cancelled'}
    raise HTTPException(status_code=404, detail='Order not found')

