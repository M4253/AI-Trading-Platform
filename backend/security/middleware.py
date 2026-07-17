"""HTTP hardening middleware for the paper-only API."""
from __future__ import annotations

import os
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Deque

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.security.auth import authenticate_bearer
from backend.security.configuration import authentication_required, is_production
from backend.security.logging import app_logger


_PUBLIC_PATHS = {'/health', '/ready', '/dependencies', '/auth/demo-login', '/openapi.json', '/docs', '/redoc'}


def _public_request(request: Request) -> bool:
    return request.method == 'OPTIONS' or request.url.path in _PUBLIC_PATHS


class RequestSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        principal = authenticate_bearer(request.headers.get('Authorization'))
        request.state.principal = principal
        if authentication_required() and not _public_request(request) and not principal:
            return JSONResponse({'detail': 'Authentication required'}, status_code=401)
        response = await call_next(request)
        response.headers['X-Request-ID'] = request.state.request_id
        app_logger().info(
            'request_completed',
            extra={
                'event': 'request_completed',
                'request_id': request.state.request_id,
                'method': request.method,
                'status_code': response.status_code,
            },
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """A bounded in-memory fixed-window limit suitable for one local process.

    A multi-instance deployment must replace this with a shared gateway or
    Redis-backed limiter; the deployment guide calls that out explicitly.
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        self._events: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _limit_for(request: Request) -> tuple[int, int]:
        if request.url.path == '/auth/demo-login':
            return 10, 60
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return int(os.getenv('WRITE_RATE_LIMIT_PER_MINUTE', '120')), 60
        return int(os.getenv('READ_RATE_LIMIT_PER_MINUTE', '300')), 60

    async def dispatch(self, request: Request, call_next) -> Response:
        if _public_request(request) and request.url.path != '/auth/demo-login':
            return await call_next(request)
        limit, window = self._limit_for(request)
        client = request.client.host if request.client else 'unknown'
        key = f'{client}:{request.method}:{request.url.path.split("/")[1:2]}'
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= max(1, limit):
                retry_after = max(1, int(window - (now - events[0])))
                response = JSONResponse({'detail': 'Rate limit exceeded'}, status_code=429)
                response.headers['Retry-After'] = str(retry_after)
                return response
            events.append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        if is_production():
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
