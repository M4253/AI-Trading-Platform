"""Small, dependency-free runtime security configuration helpers."""
from __future__ import annotations

import os


def runtime_environment() -> str:
    """Return a normalized environment name without exposing configuration values."""
    return os.getenv('APP_ENV', 'development').strip().lower() or 'development'


def is_production() -> bool:
    return runtime_environment() == 'production'


def _enabled(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def authentication_required() -> bool:
    """Fail closed outside local development unless explicitly overridden."""
    return _enabled(
        os.getenv('AUTH_REQUIRED'),
        runtime_environment() not in {'development', 'test'},
    )


def demo_auth_enabled() -> bool:
    """The fixed local demo can never be accidentally enabled in production."""
    return not is_production() and _enabled(os.getenv('DEMO_AUTH_ENABLED'), True)


def session_ttl_seconds() -> int:
    raw_value = os.getenv('SESSION_TTL_SECONDS', str(8 * 60 * 60))
    try:
        value = int(raw_value)
    except ValueError:
        value = 8 * 60 * 60
    return max(300, min(value, 24 * 60 * 60))


def cors_origins() -> list[str]:
    """Return explicit origins only; production defaults to a deny-all list."""
    configured = os.getenv('CORS_ALLOW_ORIGINS', '')
    if configured:
        origins = [origin.strip().rstrip('/') for origin in configured.split(',') if origin.strip()]
    elif is_production():
        origins = []
    else:
        origins = ['http://localhost:3000', 'http://127.0.0.1:3000']
    # Wildcards and credentialed browser sessions are deliberately not supported.
    return [origin for origin in origins if origin != '*']
