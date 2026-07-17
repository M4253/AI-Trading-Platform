import uuid
from datetime import datetime
from typing import Dict, Optional
from backend.db.db import init_db, insert_order, update_order_status, insert_trade, upsert_position_on_trade, adjust_cash, get_conn


class BrokerService:
    def __init__(self, db_path: Optional[str] = None, paper: bool = True):
        self.db_path = db_path
        init_db(db_path)
        self.paper = paper

    def _market_price(self, symbol: str) -> float:
        # In a real system, query market data. For now, return a fixed mock price or simple heuristic.
        # Simple faux price based on symbol hash
        return float(abs(hash(symbol)) % 1000) + 10.0

    def submit_order(self, symbol: str, qty: float, side: str, order_type: str = 'market', price: Optional[float] = None) -> Dict:
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

        # For paper trading or simple simulation, fill immediately
        fill_price = price if price is not None else self._market_price(symbol)
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
        # update order status
        update_order_status(order_id, 'filled', self.db_path)
        # update positions and cash
        upsert_position_on_trade(symbol, side, qty, fill_price, self.db_path)
        # For cash: buys reduce cash, sells increase cash
        cash_delta = -qty * fill_price if side.lower() == 'buy' else qty * fill_price
        adjust_cash(cash_delta, self.db_path)

        return {'order': order, 'trade': trade}

    def cancel_order(self, order_id: str) -> bool:
        return bool(__import__('backend.db.db').db.cancel_order(order_id, self.db_path))

