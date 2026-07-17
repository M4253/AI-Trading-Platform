"""Opaque, server-side sessions for the local paper dashboard.

This is intentionally a small local-session boundary, not a replacement for a
production identity provider.  The development-only demo login is disabled
when ``APP_ENV=production``; production therefore fails closed until a real
operator authentication integration is supplied.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Optional

from backend.security.configuration import demo_auth_enabled, session_ttl_seconds


@dataclass(frozen=True)
class SessionPrincipal:
    subject: str
    expires_at: int


class SessionStore:
    """In-memory server-side session registry that stores only token hashes."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionPrincipal] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def create(self, subject: str, ttl_seconds: Optional[int] = None) -> tuple[str, SessionPrincipal]:
        ttl = ttl_seconds if ttl_seconds is not None else session_ttl_seconds()
        principal = SessionPrincipal(subject=subject, expires_at=int(time.time()) + ttl)
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._purge_expired_locked()
            self._sessions[self._digest(token)] = principal
        return token, principal

    def get(self, token: str | None) -> Optional[SessionPrincipal]:
        if not token:
            return None
        digest = self._digest(token)
        with self._lock:
            principal = self._sessions.get(digest)
            if not principal or principal.expires_at <= int(time.time()):
                self._sessions.pop(digest, None)
                return None
            return principal

    def revoke(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sessions.pop(self._digest(token), None)

    def _purge_expired_locked(self) -> None:
        now = int(time.time())
        expired = [digest for digest, value in self._sessions.items() if value.expires_at <= now]
        for digest in expired:
            self._sessions.pop(digest, None)


session_store = SessionStore()


def bearer_token(authorization: str | None) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not value.strip():
        return None
    return value.strip()


def authenticate_bearer(authorization: str | None) -> Optional[SessionPrincipal]:
    return session_store.get(bearer_token(authorization))


def local_demo_login(email: str, password: str) -> tuple[str, SessionPrincipal]:
    """Issue a local opaque session only for the explicitly development demo."""
    if not demo_auth_enabled():
        raise PermissionError('Local demo login is disabled')
    expected_email = os.getenv('DEMO_LOGIN_EMAIL', 'demo@example.com')
    expected_password = os.getenv('DEMO_LOGIN_PASSWORD', 'demo')
    email_matches = hmac.compare_digest(email.strip().lower(), expected_email.strip().lower())
    password_matches = hmac.compare_digest(password, expected_password)
    if not (email_matches and password_matches):
        raise PermissionError('Invalid local demo credentials')
    return session_store.create(expected_email)
