"""Persistence for paper-only AI decision records and execution policy.

The decision log is intentionally append-oriented: an analysis is stored before
it can be approved, rejected, or automatically sent to the guarded paper
engine.  This gives the dashboard an auditable account of both trade and hold
decisions without storing credentials or contacting a broker.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.db.db import DB_LOCK, get_conn


AI_DECISION_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS ai_decisions (
        id TEXT PRIMARY KEY,
        timestamp TEXT,
        symbol TEXT,
        proposed_action TEXT,
        proposed_qty REAL,
        proposed_side TEXT,
        confidence_score REAL,
        opportunity_score REAL,
        risk_score REAL,
        expected_reward REAL,
        risk_reward_ratio REAL,
        rationale TEXT,
        inputs_json TEXT,
        model_name TEXT,
        model_version TEXT,
        prompt_version TEXT,
        decision_status TEXT,
        execution_status TEXT,
        final_order_id TEXT,
        decision_type TEXT DEFAULT 'trade',
        execution_mode TEXT DEFAULT 'manual_approval',
        model_key TEXT,
        context_json TEXT,
        reasoning_json TEXT,
        outcome TEXT,
        execution_details_json TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_decision_inputs (
        id TEXT PRIMARY KEY,
        ai_decision_id TEXT,
        input_name TEXT,
        input_value TEXT,
        input_timestamp TEXT,
        FOREIGN KEY(ai_decision_id) REFERENCES ai_decisions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_decision_audit (
        id TEXT PRIMARY KEY,
        ai_decision_id TEXT,
        stage TEXT,
        passed BOOLEAN,
        reason TEXT,
        timestamp TEXT,
        FOREIGN KEY(ai_decision_id) REFERENCES ai_decisions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_execution_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
]


_DECISION_MIGRATIONS = {
    'decision_type': "TEXT DEFAULT 'trade'",
    'execution_mode': "TEXT DEFAULT 'manual_approval'",
    'model_key': 'TEXT',
    'context_json': 'TEXT',
    'reasoning_json': 'TEXT',
    'outcome': 'TEXT',
    'execution_details_json': 'TEXT',
    'created_at': 'TEXT',
    'updated_at': 'TEXT',
}

_DEFAULT_SETTINGS = {
    'execution_mode': 'manual_approval',
    'model_key': 'rule_based_v1',
    'paper_only': 'true',
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def _ensure_parent(db_path: Optional[str]) -> None:
    if db_path:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def init_ai_db(db_path: Optional[str] = None) -> None:
    """Create and migrate AI-decision tables without destructive schema changes."""
    _ensure_parent(db_path)
    conn = get_conn(db_path)
    with DB_LOCK:
        cursor = conn.cursor()
        for sql in AI_DECISION_TABLES_SQL:
            cursor.execute(sql)

        columns = {
            row['name'] for row in cursor.execute('PRAGMA table_info(ai_decisions)').fetchall()
        }
        for name, sql_type in _DECISION_MIGRATIONS.items():
            if name not in columns:
                cursor.execute(f'ALTER TABLE ai_decisions ADD COLUMN {name} {sql_type}')

        now = _now()
        for key, value in _DEFAULT_SETTINGS.items():
            cursor.execute(
                'INSERT OR IGNORE INTO ai_execution_settings(key, value, updated_at) VALUES (?, ?, ?)',
                (key, value, now),
            )
        conn.commit()
    conn.close()


def insert_ai_decision(decision: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Persist a decision before its execution outcome is known.

    The input shape is backward compatible with the Phase 5 proposal records,
    while retaining the richer Phase 9 context and reasoning fields.
    """
    init_ai_db(db_path)
    now = _now()
    record = {
        'id': decision.get('id') or decision.get('decision_id') or str(uuid.uuid4()),
        'timestamp': decision.get('timestamp', now),
        'symbol': decision.get('symbol'),
        'proposed_action': decision.get('proposed_action', decision.get('action', 'HOLD')),
        'proposed_qty': decision.get('proposed_qty', decision.get('qty', 0)),
        'proposed_side': decision.get('proposed_side'),
        'confidence_score': decision.get('confidence_score', 0.0),
        'opportunity_score': decision.get('opportunity_score', 0.0),
        'risk_score': decision.get('risk_score', 0.0),
        'expected_reward': decision.get('expected_reward'),
        'risk_reward_ratio': decision.get('risk_reward_ratio'),
        'rationale': decision.get('rationale', ''),
        'inputs_json': _json(decision.get('inputs', {})),
        'model_name': decision.get('model_name', 'rule-based-paper-model'),
        'model_version': decision.get('model_version', '1.0'),
        'prompt_version': decision.get('prompt_version', '1.0'),
        'decision_status': decision.get('decision_status', 'awaiting_approval'),
        'execution_status': decision.get('execution_status', 'pending_approval'),
        'final_order_id': decision.get('final_order_id'),
        'decision_type': decision.get('decision_type', 'trade'),
        'execution_mode': decision.get('execution_mode', 'manual_approval'),
        'model_key': decision.get('model_key', decision.get('model_name', 'rule_based_v1')),
        'context_json': _json(decision.get('context', {})),
        'reasoning_json': _json(decision.get('reasoning', [])),
        'outcome': decision.get('outcome', 'recorded'),
        'execution_details_json': _json(decision.get('execution_details', {})),
        'created_at': decision.get('created_at', now),
        'updated_at': decision.get('updated_at', now),
    }
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            conn.execute(
                """INSERT INTO ai_decisions(
                   id, timestamp, symbol, proposed_action, proposed_qty, proposed_side,
                   confidence_score, opportunity_score, risk_score, expected_reward,
                   risk_reward_ratio, rationale, inputs_json, model_name, model_version,
                   prompt_version, decision_status, execution_status, final_order_id,
                   decision_type, execution_mode, model_key, context_json, reasoning_json,
                   outcome, execution_details_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(record.values()),
            )
            conn.commit()
    finally:
        conn.close()


def update_ai_decision_status(
    decision_id: str,
    decision_status: str,
    execution_status: str,
    order_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Backward-compatible status update used by legacy proposal callers."""
    init_ai_db(db_path)
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            conn.execute(
                """UPDATE ai_decisions
                   SET decision_status = ?, execution_status = ?, final_order_id = ?, updated_at = ?
                   WHERE id = ?""",
                (decision_status, execution_status, order_id, _now(), decision_id),
            )
            conn.commit()
    finally:
        conn.close()


def update_ai_decision_execution(
    decision_id: str,
    *,
    decision_status: str,
    execution_status: str,
    outcome: str,
    execution_details: Optional[Dict[str, Any]] = None,
    order_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Record the terminal or pending paper-execution outcome for a decision."""
    init_ai_db(db_path)
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            conn.execute(
                """UPDATE ai_decisions
                   SET decision_status = ?, execution_status = ?, outcome = ?,
                       execution_details_json = ?, final_order_id = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    decision_status,
                    execution_status,
                    outcome,
                    _json(execution_details or {}),
                    order_id,
                    _now(),
                    decision_id,
                ),
            )
            conn.commit()
    finally:
        conn.close()


def insert_ai_decision_input(
    decision_id: str,
    input_name: str,
    input_value: Any,
    input_timestamp: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    init_ai_db(db_path)
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            conn.execute(
                """INSERT INTO ai_decision_inputs
                   (id, ai_decision_id, input_name, input_value, input_timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    decision_id,
                    input_name,
                    _json(input_value) if not isinstance(input_value, str) else input_value,
                    input_timestamp or _now(),
                ),
            )
            conn.commit()
    finally:
        conn.close()


def insert_ai_audit_log(
    decision_id: str,
    stage: str,
    passed: bool,
    reason: str,
    db_path: Optional[str] = None,
) -> None:
    """Append an audit event.  The table name matches the created schema."""
    init_ai_db(db_path)
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            conn.execute(
                """INSERT INTO ai_decision_audit
                   (id, ai_decision_id, stage, passed, reason, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), decision_id, stage, bool(passed), reason, _now()),
            )
            conn.commit()
    finally:
        conn.close()


def get_ai_execution_settings(db_path: Optional[str] = None) -> Dict[str, Any]:
    init_ai_db(db_path)
    conn = get_conn(db_path)
    try:
        rows = conn.execute('SELECT key, value FROM ai_execution_settings').fetchall()
        values = {row['key']: row['value'] for row in rows}
        return {
            'execution_mode': values.get('execution_mode', 'manual_approval'),
            'model_key': values.get('model_key', 'rule_based_v1'),
            'paper_only': True,
        }
    finally:
        conn.close()


def update_ai_execution_settings(
    *, execution_mode: Optional[str] = None, model_key: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Update only safe policy fields; paper-only is intentionally immutable."""
    if execution_mode is not None and execution_mode not in {'manual_approval', 'automatic_paper'}:
        raise ValueError('Execution mode must be manual_approval or automatic_paper')
    init_ai_db(db_path)
    updates = {
        key: value for key, value in {
            'execution_mode': execution_mode,
            'model_key': model_key,
        }.items() if value is not None
    }
    if not updates:
        return get_ai_execution_settings(db_path)

    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            for key, value in updates.items():
                conn.execute(
                    """INSERT INTO ai_execution_settings(key, value, updated_at)
                       VALUES (?, ?, ?)
                       ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
                    (key, value, _now()),
                )
            conn.commit()
    finally:
        conn.close()
    return get_ai_execution_settings(db_path)


def _decode_json(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _decode_decision(row: Any) -> Dict[str, Any]:
    record = dict(row)
    record['inputs'] = _decode_json(record.get('inputs_json'), {})
    record['context'] = _decode_json(record.get('context_json'), {})
    record['reasoning'] = _decode_json(record.get('reasoning_json'), [])
    record['execution_details'] = _decode_json(record.get('execution_details_json'), {})
    return record


def get_ai_decision(decision_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    init_ai_db(db_path)
    conn = get_conn(db_path)
    try:
        row = conn.execute('SELECT * FROM ai_decisions WHERE id = ?', (decision_id,)).fetchone()
        return _decode_decision(row) if row else None
    finally:
        conn.close()


def list_ai_decisions(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    init_ai_db(db_path)
    safe_limit = max(1, min(int(limit), 200))
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            'SELECT * FROM ai_decisions ORDER BY timestamp DESC LIMIT ?', (safe_limit,)
        ).fetchall()
        return [_decode_decision(row) for row in rows]
    finally:
        conn.close()


def list_ai_decision_audit(decision_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    init_ai_db(db_path)
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            'SELECT * FROM ai_decision_audit WHERE ai_decision_id = ? ORDER BY timestamp ASC',
            (decision_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
