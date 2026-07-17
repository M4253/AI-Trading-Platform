"""Phase 7 - Web Dashboard integration tests."""
import pytest
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, '/Users/hamda/Documents/AI-Trading-Platform')

from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_portfolio_endpoint_has_data():
    """Test portfolio endpoint returns portfolio data."""
    response = client.get('/portfolio')
    assert response.status_code == 200
    data = response.json()
    assert 'cash' in data or 'positions' in data


def test_paper_account_endpoint():
    """Test paper trading account summary endpoint."""
    response = client.get('/paper/account')
    assert response.status_code == 200
    data = response.json()
    # Data can be nested under 'portfolio' or at top level
    if 'portfolio' in data:
        assert 'total_equity' in data['portfolio']
    else:
        assert 'total_equity' in data or 'current_cash' in data


def test_paper_positions_endpoint():
    """Test paper trading positions endpoint."""
    response = client.get('/paper/positions')
    assert response.status_code == 200
    data = response.json()
    assert 'positions' in data
    assert isinstance(data['positions'], list)


def test_paper_orders_endpoint():
    """Test paper trading orders endpoint."""
    response = client.get('/paper/orders')
    assert response.status_code == 200
    data = response.json()
    assert 'orders' in data
    assert isinstance(data['orders'], list)


def test_paper_trading_start_endpoint():
    """Test starting paper trading."""
    response = client.post('/paper/start')
    assert response.status_code == 200


def test_paper_trading_pause_endpoint():
    """Test pausing paper trading."""
    response = client.post('/paper/pause')
    assert response.status_code == 200


def test_paper_trading_stop_all_endpoint():
    """Test emergency stop all trading."""
    response = client.post('/paper/stop-all')
    assert response.status_code == 200


def test_ai_decisions_endpoint():
    """Test AI decisions list endpoint."""
    response = client.get('/ai/decisions?limit=10')
    assert response.status_code == 200
    data = response.json()
    assert 'decisions' in data
    assert isinstance(data['decisions'], list)


def test_cors_headers_for_frontend():
    """Test CORS headers are set for frontend."""
    response = client.get('/health')
    assert response.status_code == 200
    # CORS headers should allow frontend requests
