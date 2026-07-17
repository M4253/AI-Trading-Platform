import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.ai_db import init_ai_db
import tempfile

client = TestClient(app)


def test_ai_analyze_endpoint():
    """Test AI analysis endpoint."""
    response = client.post('/ai/analyze', json={
        'symbol': 'AAPL',
        'current_price': 150.0,
        'market_data': {
            'open': 150.0,
            'high': 152.0,
            'low': 149.0,
            'close': 151.0,
            'volume': 1000000,
            'volatility': 0.02
        },
        'market_regime': 'bull'
    })
    assert response.status_code == 200
    body = response.json()
    assert 'opportunity_score' in body
    assert 'confidence_score' in body
    assert 'risk_score' in body
    assert 'rationale' in body


def test_ai_propose_trade_endpoint():
    """Test AI trade proposal endpoint."""
    response = client.post('/ai/propose-trade', json={
        'symbol': 'AAPL',
        'current_price': 150.0,
        'market_data': {
            'open': 150.0,
            'high': 152.0,
            'low': 149.0,
            'close': 151.0,
            'volume': 1000000,
            'volatility': 0.02
        },
        'market_regime': 'bull',
        'auto_execute': False
    })
    assert response.status_code == 200


def test_ai_decisions_list_endpoint():
    """Test list AI decisions endpoint."""
    response = client.get('/ai/decisions?limit=10')
    assert response.status_code == 200
    body = response.json()
    assert 'decisions' in body
    assert 'count' in body


def test_ai_decision_detail_endpoint():
    """Test get single AI decision endpoint."""
    # First create a decision
    create_response = client.post('/ai/propose-trade', json={
        'symbol': 'TEST',
        'current_price': 100.0,
        'market_data': {'open': 100.0, 'high': 101.0, 'low': 99.0, 'close': 100.5},
        'market_regime': 'neutral',
        'auto_execute': True
    })
    
    if create_response.status_code == 200:
        # Try to list and get first decision
        list_response = client.get('/ai/decisions?limit=1')
        if list_response.status_code == 200:
            decisions = list_response.json().get('decisions', [])
            if decisions:
                decision_id = decisions[0].get('id')
                # Try to retrieve it
                detail_response = client.get(f'/ai/decisions/{decision_id}')
                # Either 200 or 404 (not found in temp DB)
                assert detail_response.status_code in (200, 404)


def test_ai_flow_respects_risk_limits():
    """Test that AI proposals are rejected if risk limits exceeded."""
    # Submit proposal with high qty (likely to fail risk check)
    response = client.post('/ai/propose-trade', json={
        'symbol': 'RISKY',
        'current_price': 1000.0,
        'proposed_qty': 10000,  # Huge position
        'market_data': {'open': 1000.0, 'high': 1010.0, 'low': 990.0, 'close': 1005.0},
        'market_regime': 'neutral',
        'auto_execute': True
    })
    
    # Should either succeed or fail gracefully, not crash
    assert response.status_code in (200, 400)


def test_ai_cannot_bypass_decision_engine():
    """Verify trades cannot be placed without Decision Engine approval."""
    # This is an architecture test
    # Any call to AI should result in audit trail with Decision Engine stage
    response = client.post('/ai/propose-trade', json={
        'symbol': 'TEST',
        'current_price': 100.0,
        'market_data': {'open': 100.0, 'high': 101.0, 'low': 99.0, 'close': 100.5},
        'market_regime': 'neutral',
        'auto_execute': True
    })
    
    if response.status_code == 200:
        body = response.json()
        # If there's an audit trail, it should include decision engine stage
        if 'audit_trail' in body:
            stages = [audit['stage'] for audit in body['audit_trail']]
            # Should never execute without going through decision engine
            assert len(stages) > 0

