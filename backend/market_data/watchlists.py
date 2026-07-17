"""Persistent local watchlists and symbol management for market intelligence."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.db.db import DB_LOCK, get_conn


WATCHLIST_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS market_watchlists (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_watchlist_symbols (
        id TEXT PRIMARY KEY,
        watchlist_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(watchlist_id, symbol),
        FOREIGN KEY(watchlist_id) REFERENCES market_watchlists(id)
    )
    """,
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not re.fullmatch(r'[A-Z0-9.\-]{1,15}', normalized):
        raise ValueError('Symbol must contain only letters, numbers, dots, or hyphens')
    return normalized


def _ensure_parent(db_path: Optional[str]) -> None:
    if db_path:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def init_watchlist_db(db_path: Optional[str] = None) -> None:
    _ensure_parent(db_path)
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            for sql in WATCHLIST_TABLES:
                conn.execute(sql)
            count = conn.execute('SELECT COUNT(*) AS count FROM market_watchlists').fetchone()['count']
            if not count:
                now = _now()
                conn.execute(
                    'INSERT INTO market_watchlists(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                    (str(uuid.uuid4()), 'Default Watchlist', now, now),
                )
            conn.commit()
    finally:
        conn.close()


def _watchlist_with_symbols(conn: Any, watchlist: Any) -> Dict[str, Any]:
    record = dict(watchlist)
    rows = conn.execute(
        'SELECT symbol FROM market_watchlist_symbols WHERE watchlist_id = ? ORDER BY symbol ASC',
        (record['id'],),
    ).fetchall()
    record['symbols'] = [row['symbol'] for row in rows]
    return record


def list_watchlists(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    init_watchlist_db(db_path)
    conn = get_conn(db_path)
    try:
        rows = conn.execute('SELECT * FROM market_watchlists ORDER BY created_at ASC').fetchall()
        return [_watchlist_with_symbols(conn, row) for row in rows]
    finally:
        conn.close()


def get_watchlist(watchlist_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    init_watchlist_db(db_path)
    conn = get_conn(db_path)
    try:
        row = conn.execute('SELECT * FROM market_watchlists WHERE id = ?', (watchlist_id,)).fetchone()
        return _watchlist_with_symbols(conn, row) if row else None
    finally:
        conn.close()


def create_watchlist(name: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    normalized = name.strip()
    if not normalized or len(normalized) > 80:
        raise ValueError('Watchlist name must be between 1 and 80 characters')
    init_watchlist_db(db_path)
    watchlist_id, now = str(uuid.uuid4()), _now()
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            conn.execute(
                'INSERT INTO market_watchlists(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
                (watchlist_id, normalized, now, now),
            )
            conn.commit()
        row = conn.execute('SELECT * FROM market_watchlists WHERE id = ?', (watchlist_id,)).fetchone()
        return _watchlist_with_symbols(conn, row)
    finally:
        conn.close()


def rename_watchlist(watchlist_id: str, name: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    normalized = name.strip()
    if not normalized or len(normalized) > 80:
        raise ValueError('Watchlist name must be between 1 and 80 characters')
    init_watchlist_db(db_path)
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            cursor = conn.execute(
                'UPDATE market_watchlists SET name = ?, updated_at = ? WHERE id = ?',
                (normalized, _now(), watchlist_id),
            )
            conn.commit()
        if cursor.rowcount != 1:
            return None
        row = conn.execute('SELECT * FROM market_watchlists WHERE id = ?', (watchlist_id,)).fetchone()
        return _watchlist_with_symbols(conn, row)
    finally:
        conn.close()


def delete_watchlist(watchlist_id: str, db_path: Optional[str] = None) -> bool:
    init_watchlist_db(db_path)
    conn = get_conn(db_path)
    try:
        with DB_LOCK:
            conn.execute('DELETE FROM market_watchlist_symbols WHERE watchlist_id = ?', (watchlist_id,))
            cursor = conn.execute('DELETE FROM market_watchlists WHERE id = ?', (watchlist_id,))
            conn.commit()
            return cursor.rowcount == 1
    finally:
        conn.close()


def add_symbol(watchlist_id: str, symbol: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    normalized = validate_symbol(symbol)
    init_watchlist_db(db_path)
    conn = get_conn(db_path)
    try:
        row = conn.execute('SELECT * FROM market_watchlists WHERE id = ?', (watchlist_id,)).fetchone()
        if not row:
            return None
        with DB_LOCK:
            conn.execute(
                'INSERT OR IGNORE INTO market_watchlist_symbols(id, watchlist_id, symbol, created_at) VALUES (?, ?, ?, ?)',
                (str(uuid.uuid4()), watchlist_id, normalized, _now()),
            )
            conn.execute('UPDATE market_watchlists SET updated_at = ? WHERE id = ?', (_now(), watchlist_id))
            conn.commit()
        return _watchlist_with_symbols(conn, row)
    finally:
        conn.close()


def remove_symbol(watchlist_id: str, symbol: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    normalized = validate_symbol(symbol)
    init_watchlist_db(db_path)
    conn = get_conn(db_path)
    try:
        row = conn.execute('SELECT * FROM market_watchlists WHERE id = ?', (watchlist_id,)).fetchone()
        if not row:
            return None
        with DB_LOCK:
            conn.execute(
                'DELETE FROM market_watchlist_symbols WHERE watchlist_id = ? AND symbol = ?',
                (watchlist_id, normalized),
            )
            conn.execute('UPDATE market_watchlists SET updated_at = ? WHERE id = ?', (_now(), watchlist_id))
            conn.commit()
        return _watchlist_with_symbols(conn, row)
    finally:
        conn.close()
