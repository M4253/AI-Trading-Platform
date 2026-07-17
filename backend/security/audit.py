"""Append-only, redacted audit records for local operational controls."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db.db import DB_LOCK, get_conn
from backend.security.logging import app_logger


CREATE_AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS security_audit_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    action TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT,
    request_id TEXT,
    details_json TEXT NOT NULL
)
"""

_SENSITIVE_MARKERS = ('secret', 'password', 'token', 'api_key', 'apikey', 'credential', 'account')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(value: Any, key: str = '') -> Any:
    """Return a serialisable audit value with credential-like fields removed."""
    if any(marker in key.lower().replace('-', '_') for marker in _SENSITIVE_MARKERS):
        return '[REDACTED]'
    if isinstance(value, dict):
        return {str(child_key): redact(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, key) for item in value]
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + '…'
    return value


def init_audit_db(db_path: Optional[str] = None) -> None:
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            conn.execute(CREATE_AUDIT_TABLE_SQL)
            conn.commit()
    finally:
        conn.close()


def record_audit_event(
    event_type: str,
    action: str,
    subject_type: str,
    subject_id: Optional[str] = None,
    *,
    request: Any = None,
    details: Optional[dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> None:
    """Record control activity without allowing audit failure to unblock or break a safety action."""
    actor = 'local-operator'
    request_id = None
    if request is not None:
        principal = getattr(request.state, 'principal', None)
        actor = getattr(principal, 'subject', actor)
        request_id = getattr(request.state, 'request_id', None)
    try:
        init_audit_db(db_path)
        conn = get_conn(db_path)
        try:
            with DB_LOCK:
                conn.execute(
                    """INSERT INTO security_audit_events
                       (id, timestamp, actor, event_type, action, subject_type, subject_id, request_id, details_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()), _now(), actor, event_type, action, subject_type,
                        subject_id, request_id, json.dumps(redact(details or {}), sort_keys=True, default=str),
                    ),
                )
                conn.commit()
        finally:
            conn.close()
    except Exception as error:  # Audit telemetry must never turn a rejected/stop action into an unsafe failure.
        app_logger().warning(
            'audit_event_persistence_failed',
            extra={'event': 'audit_event_persistence_failed', 'exception_type': type(error).__name__},
        )


def list_audit_events(limit: int = 100, db_path: Optional[str] = None) -> list[dict[str, Any]]:
    init_audit_db(db_path)
    safe_limit = max(1, min(int(limit), 200))
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            'SELECT * FROM security_audit_events ORDER BY timestamp DESC LIMIT ?', (safe_limit,)
        ).fetchall()
        records = []
        for row in rows:
            record = dict(row)
            try:
                record['details'] = json.loads(record.pop('details_json'))
            except (TypeError, json.JSONDecodeError):
                record['details'] = {}
            records.append(record)
        return records
    finally:
        conn.close()
