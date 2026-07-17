from backend.db.db import get_conn, DB_LOCK
from typing import Dict, Optional, List
from datetime import datetime
import json


BACKTEST_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        id TEXT PRIMARY KEY,
        strategy_name TEXT,
        strategy_version TEXT,
        start_date TEXT,
        end_date TEXT,
        in_sample_ratio REAL,
        initial_cash REAL,
        commission_rate REAL,
        slippage_pct REAL,
        seed INTEGER,
        created_at TEXT,
        status TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_results (
        backtest_id TEXT PRIMARY KEY,
        total_return REAL,
        annualized_return REAL,
        win_rate REAL,
        profit_factor REAL,
        sharpe_ratio REAL,
        adjusted_sharpe REAL,
        sortino_ratio REAL,
        max_drawdown REAL,
        volatility REAL,
        num_trades INTEGER,
        avg_win REAL,
        avg_loss REAL,
        final_equity REAL,
        realized_pnl REAL,
        commission_costs REAL,
        spread_costs REAL,
        slippage_costs REAL,
        exposure_time REAL,
        turnover REAL,
        result_json TEXT,
        FOREIGN KEY(backtest_id) REFERENCES backtest_runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_regime_results (
        backtest_id TEXT,
        regime TEXT,
        num_trades INTEGER,
        total_return REAL,
        profit_factor REAL,
        win_rate REAL,
        sharpe_ratio REAL,
        PRIMARY KEY(backtest_id, regime),
        FOREIGN KEY(backtest_id) REFERENCES backtest_runs(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_trades (
        id TEXT PRIMARY KEY,
        backtest_id TEXT,
        symbol TEXT,
        entry_date TEXT,
        entry_price REAL,
        exit_date TEXT,
        exit_price REAL,
        qty REAL,
        side TEXT,
        pnl REAL,
        commission REAL,
        FOREIGN KEY(backtest_id) REFERENCES backtest_runs(id)
    )
    """
]


def init_backtest_db(db_path: Optional[str] = None):
    from backend.db.db import get_conn
    conn = get_conn(db_path)
    with DB_LOCK:
        cur = conn.cursor()
        for sql in BACKTEST_TABLES_SQL:
            cur.execute(sql)
        conn.commit()


def insert_backtest_run(backtest_id: str, strategy_name: str, strategy_version: str, 
                        start_date: str, end_date: str, in_sample_ratio: float,
                        initial_cash: float, commission_rate: float, slippage_pct: float,
                        seed: int, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            """INSERT INTO backtest_runs(id, strategy_name, strategy_version, start_date, 
               end_date, in_sample_ratio, initial_cash, commission_rate, slippage_pct, seed, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (backtest_id, strategy_name, strategy_version, start_date, end_date, in_sample_ratio,
             initial_cash, commission_rate, slippage_pct, seed, datetime.utcnow().isoformat(), 'running')
        )
        conn.commit()


def insert_backtest_results(backtest_id: str, results: Dict, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            """INSERT OR REPLACE INTO backtest_results
               (backtest_id, total_return, annualized_return, win_rate, profit_factor, sharpe_ratio, 
                adjusted_sharpe, sortino_ratio, max_drawdown, volatility, num_trades, avg_win, avg_loss,
                final_equity, realized_pnl, commission_costs, spread_costs, slippage_costs, exposure_time, turnover, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (backtest_id, results.get('total_return'), results.get('annualized_return'), 
             results.get('win_rate'), results.get('profit_factor'), results.get('sharpe_ratio'),
             results.get('adjusted_sharpe'), results.get('sortino_ratio'), results.get('max_drawdown'),
             results.get('volatility'), results.get('num_trades'), results.get('avg_win'), results.get('avg_loss'),
             results.get('final_equity'), results.get('realized_pnl'), results.get('commission_costs'),
             results.get('spread_costs'), results.get('slippage_costs'), results.get('exposure_time'),
             results.get('turnover'), json.dumps(results))
        )
        conn.commit()


def insert_backtest_trade(trade_id: str, backtest_id: str, symbol: str, entry_date: str,
                          entry_price: float, exit_date: str, exit_price: float, qty: float,
                          side: str, pnl: float, commission: float, db_path: Optional[str] = None):
    conn = get_conn(db_path)
    with DB_LOCK:
        conn.execute(
            """INSERT INTO backtest_trades(id, backtest_id, symbol, entry_date, entry_price,
               exit_date, exit_price, qty, side, pnl, commission)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade_id, backtest_id, symbol, entry_date, entry_price, exit_date, exit_price, qty, side, pnl, commission)
        )
        conn.commit()

