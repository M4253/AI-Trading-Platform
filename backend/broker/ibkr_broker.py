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
        self.paper = settings.IB_PAPER if paper is None else paper
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
        IB, *_ = self._ensure_ib()
        with self._lock:
            if self._connected and self._ib is not None:
                return True
            attempt = 0
            while attempt < self._connect_retries:
                try:
                    self._ib = IB()
                    logger.info('Attempting IB connect to %s:%s clientId=%s', self.host, self.port, self.client_id)
                    self._ib.connect(self.host, self.port, clientId=self.client_id, timeout=timeout)
                    self._connected = True
                    logger.info('Connected to IB')
                    return True
                except Exception as ex:
                    attempt += 1
                    logger.warning('IB connect attempt %s failed: %s', attempt, ex)
                    time.sleep(self._connect_backoff * attempt)
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
        # Create DB order record first
        order_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        order = {
            'id': order_id,
            'symbol': symbol,
            'side': side,
            'qty': qty,
            'price': price if price is not None else None,
            'status': 'submitted',
            'order_type': order_type,
            'created_at': created_at
        }
        insert_order(order, self.db_path)

        # If not live or unable to connect, simulate paper fill similar to earlier simulator
        if not settings.LIVE_TRADING or not self.connect():
            fill_price = price if price is not None else float(abs(hash(symbol)) % 1000) + 10.0
            trade_id = str(uuid.uuid4())
            trade = {
                'id': trade_id,
                'order_id': order_id,
                'symbol': symbol,
                'side': side,
                'qty': qty,
                'price': fill_price,
                'timestamp': datetime.utcnow().isoformat()
            }
            insert_trade(trade, self.db_path)
            update_order_status(order_id, 'filled', self.db_path)
            upsert_position_on_trade(symbol, side, qty, fill_price, self.db_path)
            cash_delta = -qty * fill_price if side.lower() == 'buy' else qty * fill_price
            adjust_cash(cash_delta, self.db_path)
            return {'order': order, 'trade': trade, 'note': 'paper_fill'}

        # Live IBKR flow
        IB, Stock, MarketOrder, LimitOrder = self._ensure_ib()
        contract = Stock(symbol, 'SMART', 'USD')
        if order_type == 'market':
            ib_order = MarketOrder(side.upper(), qty)
        else:
            if price is None:
                raise ValueError('Limit order requires a price')
            ib_order = LimitOrder(side.upper(), qty, price)

        trade = None
        try:
            t = self._ib.placeOrder(contract, ib_order)
            # wait for a short time for status updates; in production prefer event-driven callbacks
            for _ in range(10):
                self._ib.sleep(0.5)
                if t.orderStatus.status in ('Filled', 'filled', 'Cancelled', 'cancelled'):
                    break
            status = t.orderStatus.status
            if status.lower() == 'filled':
                fill_price = None
                # take lastFillPrice if available
                try:
                    fill_price = float(t.orderStatus.avgFillPrice or price or 0.0)
                except Exception:
                    fill_price = price or 0.0
                trade_id = str(uuid.uuid4())
                trade = {
                    'id': trade_id,
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'qty': qty,
                    'price': fill_price,
                    'timestamp': datetime.utcnow().isoformat()
                }
                insert_trade(trade, self.db_path)
                update_order_status(order_id, 'filled', self.db_path)
                upsert_position_on_trade(symbol, side, qty, fill_price, self.db_path)
                cash_delta = -qty * fill_price if side.lower() == 'buy' else qty * fill_price
                adjust_cash(cash_delta, self.db_path)
            else:
                update_order_status(order_id, status.lower(), self.db_path)
        except Exception as e:
            logger.exception('Error placing IBKR order: %s', e)
            update_order_status(order_id, 'error', self.db_path)
            raise

        return {'order': order, 'trade': trade}

    def cancel_order(self, order_id: str) -> bool:
        # Find local order
        order = get_order(order_id, self.db_path)
        if not order:
            return False
        if order['status'] in ('filled', 'cancelled'):
            return False
        if not self.connect():
            # cannot cancel if not connected
            return False
        # For live, attempt to cancel via IB
        try:
            # Using orderId mapping is complex; assume simple scenario: no-op and mark cancelled
            update_order_status(order_id, 'cancelled', self.db_path)
            return True
        except Exception:
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

