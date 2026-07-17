"""Hardened FastAPI entry point for the paper-only trading platform.

There is intentionally no runtime path from this application to a live broker.
All orders remain local paper orders guarded by the Decision and Risk engines.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import sqlite3
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.ai_models.routes import router as ai_router
from backend.backtesting.routes import router as backtest_router
from backend.broker.broker_settings import init_broker_settings_db
from backend.broker.settings_routes import router as broker_settings_router
from backend.db.ai_db import init_ai_db
from backend.db.db import get_conn, init_db
from backend.market_data.routes import router as market_intelligence_router
from backend.market_data.watchlists import init_watchlist_db
from backend.paper_trading.paper_db import cancel_paper_order, get_paper_orders, init_paper_db
from backend.paper_trading.routes import router as paper_router
from backend.portfolio.portfolio import get_portfolio_view
from backend.security.audit import init_audit_db, list_audit_events, record_audit_event
from backend.security.auth import local_demo_login
from backend.security.configuration import cors_origins, is_production
from backend.security.logging import app_logger, configure_structured_logging
from backend.security.middleware import (
    RateLimitMiddleware,
    RequestSecurityMiddleware,
    SecurityHeadersMiddleware,
)
from backend.trading_engine.execution_engine import execute_trade_request


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TradeRequest(_StrictModel):
    symbol: str = Field(min_length=1, max_length=15, pattern=r'^[A-Za-z0-9.\-]+$')
    qty: float = Field(gt=0, le=1_000_000)
    side: Literal['buy', 'sell']
    order_type: Literal['market'] = 'market'
    price: float | None = Field(default=None, gt=0)


class CancelRequest(_StrictModel):
    order_id: str = Field(min_length=1, max_length=100)


class DemoLoginRequest(_StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


@asynccontextmanager
async def lifespan(application: FastAPI):
    configure_structured_logging()
    application.state.ready = False
    try:
        connection = init_db()
        connection.close()
        init_paper_db()
        init_ai_db()
        init_watchlist_db()
        init_broker_settings_db()
        init_audit_db()
        application.state.ready = True
        app_logger().info('application_started', extra={'event': 'application_started'})
    except Exception as error:
        # Do not expose a filesystem path or database message to API callers.
        app_logger().error(
            'application_startup_failed',
            extra={'event': 'application_startup_failed', 'exception_type': type(error).__name__},
        )
    try:
        yield
    finally:
        application.state.ready = False
        app_logger().info('application_stopped', extra={'event': 'application_stopped'})


def _safe_error_detail(error: StarletteHTTPException) -> str:
    if error.status_code >= 500:
        return 'Service temporarily unavailable'
    # API code supplies short, user-safe messages.  Do not serialise arbitrary
    # objects or exception chains into a response.
    return error.detail if isinstance(error.detail, str) else 'Request failed'


def _database_ok() -> bool:
    try:
        connection = get_conn()
        try:
            connection.execute('SELECT 1').fetchone()
            return True
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def create_app() -> FastAPI:
    application = FastAPI(
        title='AI Trading Platform',
        description='Paper-only trading platform with guarded AI decision and risk engines',
        version='1.0.0',
        lifespan=lifespan,
    )
    application.state.ready = False

    # The dashboard uses bearer sessions rather than cookies, so browser
    # credentials are never allowed cross-origin. Production has no permissive
    # fallback: CORS_ALLOW_ORIGINS must explicitly list the dashboard origin.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=False,
        allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        allow_headers=['Authorization', 'Content-Type', 'X-Request-ID'],
        max_age=600,
    )
    application.add_middleware(RequestSecurityMiddleware)
    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, error: RequestValidationError):
        del request, error
        return JSONResponse({'detail': 'Request validation failed'}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, error: StarletteHTTPException):
        del request
        return JSONResponse({'detail': _safe_error_detail(error)}, status_code=error.status_code)

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, error: Exception):
        request_id = getattr(request.state, 'request_id', None)
        app_logger().error(
            'unhandled_application_error',
            extra={
                'event': 'unhandled_application_error',
                'request_id': request_id,
                'exception_type': type(error).__name__,
            },
        )
        return JSONResponse({'detail': 'Internal service error'}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Include existing phase routers after the global protection middleware.
    application.include_router(backtest_router)
    application.include_router(ai_router)
    application.include_router(broker_settings_router)
    application.include_router(market_intelligence_router)
    application.include_router(paper_router)

    @application.post('/auth/demo-login')
    def demo_login(payload: DemoLoginRequest) -> dict[str, object]:
        """Development-only local login that returns a short-lived opaque token."""
        try:
            token, principal = local_demo_login(payload.email, payload.password)
        except PermissionError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid local demo login') from error
        return {
            'access_token': token,
            'token_type': 'bearer',
            'expires_at': principal.expires_at,
            'user': principal.subject,
            'development_only': not is_production(),
        }

    @application.get('/health')
    def health() -> dict[str, object]:
        # Keep the original minimal liveness contract stable.  Paper-only and
        # broker-lock detail live in /dependencies and /ready.
        return {'status': 'ok'}

    @application.get('/ready')
    def readiness() -> JSONResponse:
        database_ready = _database_ok()
        ready = bool(getattr(application.state, 'ready', False) and database_ready)
        payload = {
            'status': 'ready' if ready else 'not_ready',
            'database': 'available' if database_ready else 'unavailable',
            'paper_only': True,
        }
        return JSONResponse(payload, status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE)

    @application.get('/dependencies')
    def dependency_status() -> dict[str, object]:
        # These checks do not call a broker or force public-provider requests.
        return {
            'database': {'status': 'available' if _database_ok() else 'unavailable'},
            'ai_decision_engine': {'status': 'available', 'mode': 'local_rule_based'},
            'market_providers': {'status': 'configured_with_safe_fallbacks'},
            'broker': {
                'status': 'disconnected',
                'connection_testing': 'mock_only',
                'live_execution': 'locked',
            },
            'paper_only': True,
        }

    @application.get('/audit-events')
    def audit_events(limit: int = 100) -> dict[str, object]:
        return {'events': list_audit_events(limit=limit), 'paper_only': True}

    @application.post('/trade/execute')
    def trade_execute(req: TradeRequest, request: Request) -> dict[str, object]:
        """Legacy manual paper endpoint; still enters the guarded Paper Risk Engine."""
        result = execute_trade_request(req.model_dump())
        record_audit_event(
            'trade_execution',
            'paper_order_executed' if result.get('executed') else 'trade_rejected',
            'paper_trade',
            (result.get('order') or {}).get('id'),
            request=request,
            details={'symbol': req.symbol.upper(), 'side': req.side, 'rejected': bool(result.get('rejected'))},
        )
        return result

    @application.get('/portfolio')
    def portfolio() -> dict[str, object]:
        return get_portfolio_view()

    @application.get('/orders')
    def get_orders(limit: int = 50) -> list[dict[str, object]]:
        return get_paper_orders(limit=max(1, min(limit, 200)))

    @application.post('/orders/cancel')
    def post_cancel(req: CancelRequest, request: Request) -> dict[str, str]:
        success = cancel_paper_order(req.order_id)
        if not success:
            record_audit_event('trade_control', 'cancellation_rejected', 'paper_order', req.order_id, request=request)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Order not found or cannot be cancelled')
        record_audit_event('trade_control', 'order_cancelled', 'paper_order', req.order_id, request=request)
        return {'status': 'cancelled', 'order_id': req.order_id}

    return application


app = create_app()
