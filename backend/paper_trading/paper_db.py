"""Database operations for paper trading."""
from backend.db.db import get_conn, DB_LOCK
from typing import Dict, Optional, List
from datetime import datetime
import json
import uuid


PAPER_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS paper_orders (
        id TEXT PRIMARY KEY,
        symbol TEXT,
        qty REAL,
        side TEXT,
        order_type TEXT,
        price REAL,
        stop_price REAL,
        status TEXT,
        filled_qty REAL DEFAULT 0,
        avg_fill_price REAL,
        created_at TEXT,
        updated_at TEXT,
        correlation_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_trades (
        id TEXT PRIMARY KEY,
        order_id TEXT,
        symbol TEXT,
        qty REAL,
        side TEXT,
        entry_price REAL,
        exit_price REAL,
        commission REAL,
        slippage REAL,
        pnl REAL,
        entry_date TEXT,
        exit_date TEXT,
        correlation_id TEXT,
        FOREIGN KEY(order_id) REFERENCES paper_orders(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_positions (
        id TEXT PRIMARY KEY,
        symbol TEXT UNIQUE,
        qty REAL,
        avg_entry_price REAL,
        current_price REAL,
        unrealised_pnl REAL,
        created_at TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_portfolio (
        id TEXT PRIMARY KEY,
        initial_cash REAL,
        current_cash REAL,
        total_equity REAL,
        equity_high_water_mark REAL,
        total_realised_pnl REAL,
        total_unrealised_pnl REAL,
        commission_costs REAL,
        slippage_costs REAL,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_risk_events (
        id TEXT PRIMARY KEY,
        event_type TEXT,
        severity TEXT,
        description TEXT,
        guardrail_name TEXT,
        current_value REAL,
        threshold REAL,
        action_taken TEXT,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_equity_snapshots (
        id TEXT PRIMARY KEY,
        timestamp TEXT,
        equity REAL,
        cash REAL,
        positions_value REAL,
        drawdown REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_trading_state (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    )
    """
]


def init_paper_db(db_path: Optional[str] = None):
    """Initialize paper trading tables."""
    conn = get_conn(db_path)
    with DB_LOCK:
        cur = conn.cursor()
        for sql in PAPER_TABLES_SQL:
            cur.execute(sql)
        # Initialize portfolio
        cur.execute(
            "INSERT OR IGNORE INTO paper_portfolio (id, initial_cash, current_cash, total_equity, equity_high_water_mark, total_realised_pnl, total_unrealised_pnl, commission_costs, slippage_costs, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), 100000.0, 100000.0, 100000.0, 100000.0, 0.0, 0.0, 0.0, 0.0, datetime.utcnow().isoformat())
        )
        # Initialize trading state
        cur.execute("INSERT OR IGNORE INTO paper_trading_state (key, value, updated_at) VALUES (?, ?, ?)",
                   ('status', 'stopped', datetime.utcnow().isoformat()))
        conn.commit()


def insert_paper_order(order: Dict, db_path: Optional[str] = None):
    """Store paper order."""
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            """INSERT INTO paper_orders(id, symbol, qty, side, order_type, price, stop_price, status, filled_qty, avg_fill_price, created_at, updated_at, correlation_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order['id'], order['symbol'], order['qty'], order['side'], order.get('order_type', 'market'),
             order.get('price'), order.get('stop_price'), 'pending', 0.0, 0.0,
             datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), order.get('correlation_id', str(uuid.uuid4())))
        )
        conn.commit()


def update_paper_order_status(order_id: str, status: str, filled_qty: float = None, avg_price: float = None, db_path: Optional[str] = None):
    """Update paper order status."""
    conn = get_conn(db_path)
    with DB_LOCK:
        if filled_qty is not None and avg_price is not None:
            conn.execute(
                "UPDATE paper_orders SET status = ?, filled_qty = ?, avg_fill_price = ?, updated_at = ? WHERE id = ?",
                (status, filled_qty, avg_price, datetime.utcnow().isoformat(), order_id)
            )
        else:
            conn.execute(
                "UPDATE paper_orders SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.utcnow().isoformat(), order_id)
            )
        conn.commit()


def insert_paper_trade(trade: Dict, db_path: Optional[str] = None):
    """Store paper trade."""
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            """INSERT INTO paper_trades(id, order_id, symbol, qty, side, entry_price, exit_price, commission, slippage, pnl, entry_date, exit_date, correlation_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade['id'], trade.get('order_id'), trade['symbol'], trade['qty'], trade['side'],
             trade.get('entry_price'), trade.get('exit_price'), trade.get('commission', 0),
             trade.get('slippage', 0), trade.get('pnl', 0),
             trade.get('entry_date', datetime.utcnow().isoformat()),
             trade.get('exit_date'), trade.get('correlation_id', str(uuid.uuid4())))
        )
        conn.commit()


def get_paper_orders(limit: int = 50, db_path: Optional[str] = None) -> List[Dict]:
    """Get paper orders."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM paper_orders ORDER BY created_at DESC LIMIT ?", (limit,))
    return [dict(row) for row in cur.fetchall()]


def get_paper_positions(db_path: Optional[str] = None) -> List[Dict]:
    """Get current positions."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM paper_positions WHERE qty != 0")
    return [dict(row) for row in cur.fetchall()]


def get_paper_portfolio(db_path: Optional[str] = None) -> Optional[Dict]:
    """Get portfolio summary."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM paper_portfolio LIMIT 1")
    row = cur.fetchone()
    return dict(row) if row else None


def update_paper_portfolio(updates: Dict, db_path: Optional[str] = None):
    """Update portfolio metrics."""
    conn = get_conn(db_path)
    with DB_LOCK:
        portfolio = get_paper_portfolio(db_path)
        if not portfolio:
            return
        
        # Build update query
        update_fields = []
        values = []
        for key, value in updates.items():
            update_fields.append(f"{key} = ?")
            values.append(value)
        
        update_fields.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(portfolio['id'])
        
        query = f"UPDATE paper_portfolio SET {', '.join(update_fields)} WHERE id = ?"
        conn.execute(query, values)
        conn.commit()


def insert_risk_event(event: Dict, db_path: Optional[str] = None):
    """Log risk event."""
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            """INSERT INTO paper_risk_events(id, event_type, severity, description, guardrail_name, current_value, threshold, action_taken, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), event['event_type'], event.get('severity', 'info'),
             event.get('description'), event.get('guardrail_name'),
             event.get('current_value'), event.get('threshold'),
             event.get('action_taken'), datetime.utcnow().isoformat())
        )
        conn.commit()


def get_paper_trading_state(key: str, db_path: Optional[str] = None) -> Optional[str]:
    """Get trading state."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM paper_trading_state WHERE key = ?", (key,))
    row = cur.fetchone()
    return row[0] if row else None


def set_paper_trading_state(key: str, value: str, db_path: Optional[str] = None):
    """Set trading state."""
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            "INSERT OR REPLACE INTO paper_trading_state(key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.utcnow().isoformat())
        )
        conn.commit()
