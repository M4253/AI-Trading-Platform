from typing import Optional, Dict
from backend.config.settings import settings

if settings.LIVE_TRADING:
    from backend.broker.ibkr_broker import IBKRBroker as _BrokerImpl
else:
    # fallback simulated broker (simple immediate-fill simulator)
    import uuid
    from datetime import datetime
    from backend.db.db import init_db, insert_order, update_order_status, insert_trade, upsert_position_on_trade, adjust_cash

    class _BrokerImpl:
        def __init__(self, db_path: Optional[str] = None, paper: bool = True):
            init_db(db_path)
            self.db_path = db_path
            self.paper = paper

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
            return {'order': order, 'trade': trade}

        def cancel_order(self, order_id: str) -> bool:
            from backend.db.db import cancel_order
            return cancel_order(order_id, self.db_path)

        def get_positions(self):
            from backend.db.db import get_portfolio
            return get_portfolio(self.db_path)

        def get_account_balance(self):
            from backend.db.db import get_portfolio
            return get_portfolio(self.db_path)


class BrokerService(_BrokerImpl):
    """Facade class. Instantiates either IBKR-backed broker or simulated broker depending on settings."""
    pass

