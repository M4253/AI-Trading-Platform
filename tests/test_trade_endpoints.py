from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_trade_execute_and_portfolio_and_orders_and_cancel():
    # Execute a buy trade
    resp = client.post('/trade/execute', json={'symbol': 'AAPL', 'qty': 1, 'side': 'buy'})
    assert resp.status_code == 200
    body = resp.json()
    assert 'order' in body and 'trade' in body
    order_id = body['order']['id']

    # Get orders
    resp2 = client.get('/orders')
    assert resp2.status_code == 200
    orders = resp2.json()
    assert any(o['id'] == order_id for o in orders)

    # Get portfolio
    resp3 = client.get('/portfolio')
    assert resp3.status_code == 200
    pf = resp3.json()
    assert 'cash' in pf and 'positions' in pf

    # Try cancel (should fail because already filled)
    resp4 = client.post('/orders/cancel', json={'order_id': order_id})
    assert resp4.status_code == 404


def test_health():
    resp = client.get('/health')
    assert resp.status_code == 200
    body = resp.json()
    assert body.get('status') in ('ok', 'healthy')
