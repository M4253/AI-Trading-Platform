"""Local, credential-free broker configuration storage for the dashboard.

These records intentionally contain only connection metadata (name, host,
port, client id, and an optional local label).  API keys, passwords, account
numbers, and other real broker credentials are neither accepted nor stored.
All connection tests are deterministic mock checks; this module never imports
or invokes the IBKR client.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


DEFAULT_BROKER_SETTINGS_DB = 'backend/data/broker_settings.db'
DB_LOCK = threading.Lock()


class BrokerConfigurationInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    broker: Literal['interactive_brokers'] = 'interactive_brokers'
    mode: Literal['paper', 'live'] = 'paper'
    host: str = Field(default='127.0.0.1', min_length=1, max_length=255)
    port: int = Field(default=7497, ge=1, le=65535)
    client_id: int = Field(default=1, ge=1, le=2147483647)
    profile_label: str = Field(default='', max_length=120)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS broker_configurations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    broker TEXT NOT NULL,
    mode TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    profile_label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    last_mock_tested_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_db_path(db_path: Optional[str] = None) -> str:
    return db_path or DEFAULT_BROKER_SETTINGS_DB


def _connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = _resolve_db_path(db_path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    # Settings contain no secrets, but the local file is still private to the
    # current user where the operating system supports POSIX permissions.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return connection


def init_broker_settings_db(db_path: Optional[str] = None) -> None:
    connection = _connection(db_path)
    with DB_LOCK:
        connection.execute(CREATE_TABLE_SQL)
        connection.commit()
    connection.close()


def _clean_input(configuration: BrokerConfigurationInput) -> dict[str, Any]:
    values = configuration.model_dump()
    values['name'] = values['name'].strip()
    values['host'] = values['host'].strip()
    values['profile_label'] = values['profile_label'].strip()
    if not values['name'] or not values['host']:
        raise ValueError('Configuration name and host are required')
    return values


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _get_configuration_row(config_id: str, db_path: Optional[str] = None) -> Optional[sqlite3.Row]:
    connection = _connection(db_path)
    try:
        row = connection.execute(
            'SELECT * FROM broker_configurations WHERE id = ?', (config_id,)
        ).fetchone()
        return row
    finally:
        connection.close()


def list_broker_configurations(db_path: Optional[str] = None) -> list[dict[str, Any]]:
    init_broker_settings_db(db_path)
    connection = _connection(db_path)
    try:
        rows = connection.execute(
            'SELECT * FROM broker_configurations ORDER BY created_at DESC'
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        connection.close()


def create_broker_configuration(
    configuration: BrokerConfigurationInput, db_path: Optional[str] = None
) -> dict[str, Any]:
    init_broker_settings_db(db_path)
    values = _clean_input(configuration)
    now = _now()
    config_id = str(uuid.uuid4())
    status = 'live_locked' if values['mode'] == 'live' else 'disconnected'
    connection = _connection(db_path)
    try:
        with DB_LOCK:
            connection.execute(
                """INSERT INTO broker_configurations
                   (id, name, broker, mode, host, port, client_id, profile_label,
                    status, last_mock_tested_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
                (config_id, values['name'], values['broker'], values['mode'],
                 values['host'], values['port'], values['client_id'],
                 values['profile_label'], status, now, now),
            )
            connection.commit()
        row = connection.execute(
            'SELECT * FROM broker_configurations WHERE id = ?', (config_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        connection.close()


def update_broker_configuration(
    config_id: str, configuration: BrokerConfigurationInput, db_path: Optional[str] = None
) -> Optional[dict[str, Any]]:
    init_broker_settings_db(db_path)
    values = _clean_input(configuration)
    existing = _get_configuration_row(config_id, db_path)
    if not existing:
        return None

    # Changing any connection setting revokes a prior mock-ready result.
    status = 'live_locked' if values['mode'] == 'live' else 'disconnected'
    now = _now()
    connection = _connection(db_path)
    try:
        with DB_LOCK:
            connection.execute(
                """UPDATE broker_configurations
                   SET name = ?, broker = ?, mode = ?, host = ?, port = ?,
                       client_id = ?, profile_label = ?, status = ?,
                       last_mock_tested_at = NULL, updated_at = ?
                   WHERE id = ?""",
                (values['name'], values['broker'], values['mode'], values['host'],
                 values['port'], values['client_id'], values['profile_label'],
                 status, now, config_id),
            )
            connection.commit()
        row = connection.execute(
            'SELECT * FROM broker_configurations WHERE id = ?', (config_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        connection.close()


def delete_broker_configuration(config_id: str, db_path: Optional[str] = None) -> bool:
    init_broker_settings_db(db_path)
    connection = _connection(db_path)
    try:
        with DB_LOCK:
            cursor = connection.execute(
                'DELETE FROM broker_configurations WHERE id = ?', (config_id,)
            )
            connection.commit()
            return cursor.rowcount == 1
    finally:
        connection.close()


def run_mock_connection_test(
    config_id: str, db_path: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """Validate a saved configuration without a network or broker call."""
    init_broker_settings_db(db_path)
    configuration = _get_configuration_row(config_id, db_path)
    if not configuration:
        return None
    config = _row_to_dict(configuration)

    if config['mode'] == 'live':
        return {
            'configuration': config,
            'test_mode': 'mock',
            'status': 'live_locked',
            'message': 'Live trading is locked. No IBKR connection was attempted.',
        }

    tested_at = _now()
    connection = _connection(db_path)
    try:
        with DB_LOCK:
            connection.execute(
                """UPDATE broker_configurations
                   SET status = ?, last_mock_tested_at = ?, updated_at = ?
                   WHERE id = ?""",
                ('paper_ready', tested_at, tested_at, config_id),
            )
            connection.commit()
        updated = connection.execute(
            'SELECT * FROM broker_configurations WHERE id = ?', (config_id,)
        ).fetchone()
        return {
            'configuration': _row_to_dict(updated),
            'test_mode': 'mock',
            'status': 'paper_ready',
            'message': 'Mock test passed. Paper configuration is ready; IBKR remains disconnected.',
        }
    finally:
        connection.close()
