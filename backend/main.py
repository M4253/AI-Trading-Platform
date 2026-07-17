import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.trading_engine.execution_engine import execute_trade_request
from backend.portfolio.portfolio import get_portfolio_view
from backend.paper_trading.paper_db import get_paper_orders, cancel_paper_order
from backend.backtesting.routes import router as backtest_router
from backend.ai_models.routes import router as ai_router
from backend.paper_trading.routes import router as paper_router

app = FastAPI(
    title="AI Trading Platform",
    description="Production AI trading platform with Decision Engine, Risk Management, and Paper Trading",
    version="1.0.0"
)

# Permit the local dashboard explicitly.  The demo uses bearer tokens rather
# than cookies, so credentialed wildcard CORS is neither needed nor safe.
frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        'CORS_ALLOW_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000',
    ).split(',')
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(backtest_router)
app.include_router(ai_router)
app.include_router(paper_router)


class TradeRequest(BaseModel):
    symbol: str
    qty: float
    side: str
    order_type: str = 'market'
    price: float | None = None


class CancelRequest(BaseModel):
    order_id: str


@app.get('/health')
def health():
    return {"status": "ok"}


@app.post('/trade/execute')
def trade_execute(req: TradeRequest):
    result = execute_trade_request(req.dict())
    return result


@app.get('/portfolio')
def portfolio():
    return get_portfolio_view()


@app.get('/orders')
def get_orders():
    return get_paper_orders()


@app.post('/orders/cancel')
def post_cancel(req: CancelRequest):
    success = cancel_paper_order(req.order_id)
    if not success:
        raise HTTPException(status_code=404, detail='Order not found or cannot be cancelled')
    return {'status': 'cancelled', 'order_id': req.order_id}
