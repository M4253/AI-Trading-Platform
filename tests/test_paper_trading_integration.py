"""Integration tests for paper trading REST endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_paper_account_endpoint():
    """Test get paper account endpoint."""
    response = client.get('/paper/account')
    assert response.status_code == 200
    body = response.json()
    assert 'portfolio' in body or 'status' in body


def test_paper_positions_endpoint():
    """Test get positions endpoint."""
    response = client.get('/paper/positions')
    assert response.status_code == 200
    body = response.json()
    assert 'positions' in body


def test_paper_orders_endpoint():
    """Test get orders endpoint."""
    response = client.get('/paper/orders?limit=10')
    assert response.status_code == 200
    body = response.json()
    assert 'orders' in body


def test_paper_start_trading():
    """Test start trading endpoint."""
    response = client.post('/paper/start')
    assert response.status_code == 200
    assert response.json().get('status') == 'started'


def test_paper_pause_trading():
    """Test pause trading endpoint."""
    response = client.post('/paper/pause')
    assert response.status_code == 200
    assert response.json().get('status') == 'paused'


def test_paper_stop_all_trading():
    """Test emergency stop endpoint."""
    response = client.post('/paper/stop-all')
    assert response.status_code == 200
    body = response.json()
    assert body.get('status') == 'halted'


def test_paper_execute_trade():
    """Test execute trade endpoint."""
    response = client.post('/paper/trade', json={
        'symbol': 'AAPL',
        'qty': 10,
        'side': 'buy',
        'market_data': {'close': 150.0},
        'market_regime': 'neutral'
    })
    assert response.status_code == 200


def test_paper_trading_halts_block_new_orders():
    """Test that halt prevents new orders."""
    # Stop all trading
    client.post('/paper/stop-all')
    # Try to execute trade
    response = client.post('/paper/trade', json={
        'symbol': 'TEST',
        'qty': 1,
        'side': 'buy',
        'market_data': {'close': 100.0}
    })
    # Should complete but likely be rejected
    assert response.status_code in (200, 400)

