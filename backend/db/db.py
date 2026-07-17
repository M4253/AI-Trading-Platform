import sqlite3
import threading
from typing import Optional, List, Dict
from datetime import datetime

DB_LOCK = threading.Lock()

DEFAULT_DB = 'backend/data/trading.db'

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        symbol TEXT,
        side TEXT,
        qty REAL,
        price REAL,
        status TEXT,
        order_type TEXT,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY,
        order_id TEXT,
        symbol TEXT,
        side TEXT,
        qty REAL,
        price REAL,
        timestamp TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        symbol TEXT PRIMARY KEY,
        qty REAL,
        avg_price REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_state (
        key TEXT PRIMARY KEY,
        value REAL
    )
    """
]


def get_conn(db_path: Optional[str] = None):
    if not db_path:
        db_path = DEFAULT_DB
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # enforce foreign keys if needed
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db(db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        cur = conn.cursor()
        for sql in CREATE_TABLES_SQL:
            cur.execute(sql)
        # ensure portfolio cash exists
        cur.execute("INSERT OR IGNORE INTO portfolio_state(key, value) VALUES ('cash', 100000.0)")
        conn.commit()
    return conn


def insert_order(order: Dict, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            "INSERT INTO orders(id, symbol, side, qty, price, status, order_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (order['id'], order['symbol'], order['side'], order['qty'], order.get('price'), order['status'], order.get('order_type', 'market'), order.get('created_at', datetime.utcnow().isoformat()))
        )
        conn.commit()


def update_order_status(order_id: str, status: str, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()


def insert_trade(trade: Dict, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            "INSERT INTO trades(id, order_id, symbol, side, qty, price, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade['id'], trade['order_id'], trade['symbol'], trade['side'], trade['qty'], trade['price'], trade.get('timestamp', datetime.utcnow().isoformat()))
        )
        conn.commit()


def upsert_position_on_trade(symbol: str, side: str, qty: float, price: float, db_path: Optional[str] = None):
    # buy increases position, sell decreases
    conn = get_conn(db_path)
    with DB_LOCK:
        cur = conn.cursor()
        cur.execute('SELECT qty, avg_price FROM positions WHERE symbol = ?', (symbol,))
        row = cur.fetchone()
        signed_qty = qty if side.lower() == 'buy' else -qty
        if row is None:
            # new position
            cur.execute('INSERT INTO positions(symbol, qty, avg_price) VALUES (?, ?, ?)', (symbol, signed_qty, price))
        else:
            prev_qty = row['qty']
            prev_avg = row['avg_price']
            new_qty = prev_qty + signed_qty
            if new_qty == 0:
                # closed position
                cur.execute('DELETE FROM positions WHERE symbol = ?', (symbol,))
            elif (prev_qty >= 0 and signed_qty >= 0) or (prev_qty <= 0 and signed_qty <= 0):
                # increasing in same direction -> new weighted avg
                total_cost = prev_avg * prev_qty + price * signed_qty
                avg_price = total_cost / new_qty
                cur.execute('UPDATE positions SET qty = ?, avg_price = ? WHERE symbol = ?', (new_qty, avg_price, symbol))
            else:
                # reducing or flipping direction -> keep avg price for remaining qty
                cur.execute('UPDATE positions SET qty = ? WHERE symbol = ?', (new_qty, symbol))
        conn.commit()


def adjust_cash(delta: float, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO portfolio_state(key, value) VALUES ('cash', 100000.0)")
        cur.execute('UPDATE portfolio_state SET value = value + ? WHERE key = ?', (delta, 'cash'))
        conn.commit()


def list_orders(db_path: Optional[str] = None) -> List[Dict]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM orders ORDER BY created_at DESC')
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_portfolio(db_path: Optional[str] = None) -> Dict:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM portfolio_state WHERE key = 'cash'")
    row = cur.fetchone()
    cash = row['value'] if row else 0.0
    cur.execute('SELECT symbol, qty, avg_price FROM positions')
    positions = [dict(r) for r in cur.fetchall()]
    # compute simple P&L: unrealized using last trade price or avg_price (no market data here)
    pnl = 0.0
    return {'cash': cash, 'positions': positions, 'unrealized_pnl': pnl}


def get_order(order_id: str, db_path: Optional[str] = None) -> Optional[Dict]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def cancel_order(order_id: str, db_path: Optional[str] = None) -> bool:
    conn = get_conn(db_path)
    with DB_LOCK:
        cur = conn.cursor()
        cur.execute('SELECT status FROM orders WHERE id = ?', (order_id,))
        row = cur.fetchone()
        if not row:
            return False
        status = row['status']
        if status in ('filled', 'cancelled'):
            return False
        cur.execute('UPDATE orders SET status = ? WHERE id = ?', ('cancelled', order_id))
        conn.commit()
        return True
