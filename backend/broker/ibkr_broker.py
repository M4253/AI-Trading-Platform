import os
import time
import threading
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from backend.config.settings import settings
from backend.db.db import init_db, insert_order, update_order_status, insert_trade, upsert_position_on_trade, adjust_cash, get_order, get_conn

logger = logging.getLogger(__name__)


class IBKRBroker:
    def __init__(self, db_path: Optional[str] = None, paper: Optional[bool] = None, host: Optional[str] = None, port: Optional[int] = None, client_id: Optional[int] = None):
        init_db(db_path or settings.DB_PATH)
        self.db_path = db_path or settings.DB_PATH
        self.paper = True
        self.host = host or settings.IB_HOST
        self.port = port or settings.IB_PORT
        self.client_id = client_id or settings.IB_CLIENT_ID
        self._ib = None
        self._connected = False
        self._lock = threading.Lock()
        self._connect_retries = 3
        self._connect_backoff = 2

    def _ensure_ib(self):
        try:
            from ib_insync import IB, Stock, MarketOrder, LimitOrder
        except Exception as e:
            raise RuntimeError('ib_insync library is required for IBKRBroker') from e
        return IB, Stock, MarketOrder, LimitOrder

    def connect(self, timeout: int = 5) -> bool:
        """Always remain disconnected until a separately verified go-live phase.

        This deliberately does not import ``ib_insync`` or open a socket, even
        when callers pass a host, port, or ``paper=False``.
        """
        logger.info('IBKR connection requested while broker integration is disabled')
        self._connected = False
        return False

    def disconnect(self):
        with self._lock:
            if self._ib:
                try:
                    self._ib.disconnect()
                except Exception:
                    pass
            self._ib = None
            self._connected = False

    def _to_contract(self, symbol: str):
        _, Stock, *_ = self._ensure_ib()
        # SMART routing, USD
        return Stock(symbol, 'SMART', 'USD')

    def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market', price: Optional[float] = None) -> Dict[str, Any]:
        raise RuntimeError(
            'IBKR order execution is disabled. Use the PaperTradingEngine; '
            'real IBKR verification has not been performed.'
        )

    def cancel_order(self, order_id: str) -> bool:
        return False

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self.connect():
            # return cached positions from DB
            conn = get_conn(self.db_path)
            cur = conn.cursor()
            cur.execute('SELECT symbol, qty, avg_price FROM positions')
            return [dict(r) for r in cur.fetchall()]
        try:
            positions = self._ib.positions()
            # transform
            out = []
            for p in positions:
                out.append({'symbol': p.contract.symbol, 'qty': p.position, 'avg_price': None})
            return out
        except Exception:
            return []

    def get_account_balance(self) -> Dict[str, float]:
        if not self.connect():
            from backend.db.db import get_portfolio
            return get_portfolio(self.db_path)
        try:
            summary = self._ib.accountSummary()
            # Transform into dict (simplified)
            bal = {item.tag: float(item.value) for item in summary}
            return bal
        except Exception:
            return {}
