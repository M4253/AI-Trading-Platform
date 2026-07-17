from typing import Dict
from backend.broker.broker_service import BrokerService

# Simple AI decision engine that routes orders to the broker service.
# In a real system this would contain model inference and risk checks.

broker = BrokerService(paper=True)


def decide_and_execute(signal: Dict) -> Dict:
    # signal expected to have: symbol, qty, side
    symbol = signal.get('symbol')
    qty = float(signal.get('qty', 0))
    side = signal.get('side')
    order_type = signal.get('order_type', 'market')
    price = signal.get('price')
    return broker.submit_order(symbol, qty, side, order_type=order_type, price=price)
