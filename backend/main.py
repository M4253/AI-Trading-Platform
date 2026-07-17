from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from backend.trading_engine.execution_engine import execute_trade_request
from backend.portfolio.portfolio import get_portfolio_view
from backend.db.db import list_orders, cancel_order

app = FastAPI()


@app.get('/health')
def health():
    return {"status": "ok"}


class TradeRequest(BaseModel):
    symbol: str
    qty: float
    side: str
    order_type: str = 'market'
    price: float | None = None


class CancelRequest(BaseModel):
    order_id: str


@app.post('/trade/execute')
def trade_execute(req: TradeRequest):
    result = execute_trade_request(req.dict())
    return result


@app.get('/portfolio')
def portfolio():
    return get_portfolio_view()


@app.get('/orders')
def get_orders():
    return list_orders()


@app.post('/orders/cancel')
def post_cancel(req: CancelRequest):
    success = cancel_order(req.order_id)
    if not success:
        raise HTTPException(status_code=404, detail='Order not found or cannot be cancelled')
    return {'status': 'cancelled', 'order_id': req.order_id}
