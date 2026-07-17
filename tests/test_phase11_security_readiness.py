"""Phase 11 security, reliability, recovery, and paper-only gate coverage."""
from __future__ import annotations

from datetime import date, timedelta
from fastapi.testclient import TestClient
import pytest

from backend.db import db as db_module
from backend.main import create_app
from backend.market_data import routes as market_routes
from backend.market_data.market_data_service import MarketIntelligenceService
from backend.paper_trading.paper_engine import PaperTradingEngine
from backend.security.audit import list_audit_events, record_audit_event
from backend.security.secret_store import DisabledSecretStore, SecretStorageUnavailable


@pytest.fixture
def isolated_runtime(monkeypatch, tmp_path):
    database_path = str(tmp_path / 'phase11.db')
    monkeypatch.setattr(db_module, 'DEFAULT_DB', database_path)
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('AUTH_REQUIRED', raising=False)
    monkeypatch.delenv('WRITE_RATE_LIMIT_PER_MINUTE', raising=False)
    return database_path


def test_production_is_fail_closed_for_auth_demo_and_cors(monkeypatch, tmp_path):
    monkeypatch.setattr(db_module, 'DEFAULT_DB', str(tmp_path / 'production.db'))
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('AUTH_REQUIRED', raising=False)
    monkeypatch.setenv('CORS_ALLOW_ORIGINS', 'https://dashboard.example.test')

    with TestClient(create_app()) as client:
        assert client.get('/portfolio').status_code == 401
        assert client.post('/auth/demo-login', json={'email': 'demo@example.com', 'password': 'demo'}).status_code == 401
        assert client.get('/health').status_code == 200
        allowed = client.get('/health', headers={'Origin': 'https://dashboard.example.test'})
        denied = client.get('/health', headers={'Origin': 'https://untrusted.example.test'})
        assert allowed.headers['access-control-allow-origin'] == 'https://dashboard.example.test'
        assert 'access-control-allow-origin' not in denied.headers
        assert 'strict-transport-security' in allowed.headers


def test_opaque_demo_session_and_security_headers(isolated_runtime):
    with TestClient(create_app()) as client:
        login = client.post('/auth/demo-login', json={'email': 'demo@example.com', 'password': 'demo'})
        assert login.status_code == 200
        payload = login.json()
        assert payload['access_token']
        assert payload['access_token'] != 'demo'
        assert payload['development_only'] is True
        health = client.get('/health')
        assert health.headers['x-content-type-options'] == 'nosniff'
        assert health.headers['x-frame-options'] == 'DENY'
        assert "frame-ancestors 'none'" in health.headers['content-security-policy']
        assert health.headers['x-request-id']


def test_audit_events_are_redacted_and_cover_emergency_and_rejected_controls(isolated_runtime):
    with TestClient(create_app()) as client:
        assert client.post('/paper/start').status_code == 200
        assert client.post('/paper/stop-all').status_code == 200
        rejected = client.post('/paper/trade', json={
            'symbol': 'AAPL', 'qty': 1, 'side': 'buy', 'market_data': {'close': 100},
        })
        assert rejected.status_code == 200
        assert rejected.json()['rejected'] is True

    record_audit_event(
        'settings_change', 'secret_test', 'configuration', 'local',
        details={'api_key': 'must-not-be-stored', 'nested': {'password': 'must-not-be-stored'}},
        db_path=isolated_runtime,
    )
    events = list_audit_events(db_path=isolated_runtime)
    actions = {event['action'] for event in events}
    assert {'all_new_orders_blocked', 'trade_rejected', 'secret_test'} <= actions
    redacted = next(event for event in events if event['action'] == 'secret_test')
    assert redacted['details']['api_key'] == '[REDACTED]'
    assert redacted['details']['nested']['password'] == '[REDACTED]'


def test_restart_recovers_paper_state_and_stop_blocks_every_new_order(isolated_runtime):
    with TestClient(create_app()) as first_client:
        assert first_client.post('/paper/start').status_code == 200
        trade = first_client.post('/paper/trade', json={
            'symbol': 'AAPL', 'qty': 1, 'side': 'buy', 'market_data': {'close': 100},
        })
        assert trade.json()['executed'] is True

    # A fresh app instance uses the same persistent local database.
    with TestClient(create_app()) as second_client:
        account = second_client.get('/paper/account').json()
        assert account['status'] == 'running'
        assert second_client.post('/paper/stop-all').status_code == 200
        orders_before = len(second_client.get('/paper/orders').json()['orders'])
        blocked = second_client.post('/paper/trade', json={
            'symbol': 'MSFT', 'qty': 1, 'side': 'buy', 'market_data': {'close': 100},
        })
        assert blocked.json()['rejected'] is True
        assert 'halted' in blocked.json()['reason'].lower()
        assert len(second_client.get('/paper/orders').json()['orders']) == orders_before


def test_ai_approval_after_stop_is_persisted_as_paper_rejected(isolated_runtime):
    context = {
        'symbol': 'AAPL',
        'current_price': 109.0,
        'market_data': {'open': 100.0, 'close': 109.0, 'volume': 1_500_000, 'volatility': 0.01},
        'chart_data': {'closes': [100, 101, 102, 103, 105, 106, 107, 109]},
        'indicators': {'rsi': 65, 'macd': 0.03},
        'news': [{'headline': 'Record profit growth receives an upgrade'}],
    }
    with TestClient(create_app()) as client:
        assert client.post('/paper/start').status_code == 200
        created = client.post('/ai/decisions', json=context)
        assert created.status_code == 201
        decision_id = created.json()['id']
        assert client.post('/paper/stop-all').status_code == 200
        approved = client.post(f'/ai/decisions/{decision_id}/approve')
        assert approved.status_code == 200
        assert approved.json()['execution_status'] == 'paper_rejected'
        assert approved.json()['outcome'] == 'paper_execution_rejected'


def test_complete_market_context_to_persisted_paper_execution_flow(isolated_runtime, monkeypatch):
    """Exercise the dashboard-facing chain without a network provider or broker."""
    class MarketProvider:
        name = 'phase11_fixture_market'
        is_free = True

        def get_daily_bars(self, symbol):
            return [
                {
                    'date': (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
                    'open': 100 + index,
                    'high': 101 + index,
                    'low': 99 + index,
                    'close': 100.8 + index,
                    'volume': 1_000_000,
                }
                for index in range(30)
            ]

    class NewsProvider:
        name = 'phase11_fixture_news'
        is_free = True

        def get_headlines(self, symbol, limit=10):
            return [{'headline': f'{symbol} reports record profit growth and receives an upgrade'}]

    class CalendarProvider:
        name = 'phase11_fixture_calendar'
        is_free = True

        def get_events(self, days=14):
            return []

    monkeypatch.setattr(
        market_routes,
        '_market_intelligence',
        MarketIntelligenceService(
            market_providers=[MarketProvider()],
            news_providers=[NewsProvider()],
            calendar_providers=[CalendarProvider()],
        ),
    )

    with TestClient(create_app()) as client:
        assert client.post('/paper/start').status_code == 200
        watchlist = client.get('/market/watchlists').json()['watchlists'][0]
        assert client.post(f"/market/watchlists/{watchlist['id']}/symbols", json={'symbol': 'AAPL'}).status_code == 200
        context = client.get('/market/context/AAPL')
        assert context.status_code == 200
        assert context.json()['ai_context']['news']

        proposal = client.post('/market/ai-decisions/AAPL')
        assert proposal.status_code == 201
        decision = proposal.json()['decision']
        assert decision['execution_status'] == 'pending_approval'

        approved = client.post(f"/ai/decisions/{decision['id']}/approve")
        assert approved.status_code == 200
        assert approved.json()['execution_status'] == 'paper_executed'

        # These are the persisted dashboard read models, not an in-memory result.
        stored = client.get(f"/ai/decisions/{decision['id']}").json()
        assert stored['audit_trail']
        assert stored['final_order_id']
        assert any(order['id'] == stored['final_order_id'] for order in client.get('/paper/orders').json()['orders'])
        assert client.get('/portfolio').json()['paper_trading'] is True


def test_rate_limit_and_safe_execution_failure(isolated_runtime, monkeypatch):
    monkeypatch.setenv('WRITE_RATE_LIMIT_PER_MINUTE', '1')
    with TestClient(create_app()) as client:
        assert client.post('/paper/start').status_code == 200
        limited = client.post('/paper/pause')
        assert limited.status_code == 429
        assert limited.json() == {'detail': 'Rate limit exceeded'}

    engine = PaperTradingEngine(db_path=isolated_runtime)
    engine.start_trading()

    class FailingPaperBroker:
        def submit_market_order(self, *args, **kwargs):
            raise RuntimeError('/private/path/that-must-not-reach-client')

    engine.broker = FailingPaperBroker()
    result = engine.execute_trade('AAPL', 1, 'buy', {'close': 100}, {'total_equity': 100_000})
    assert result['rejected'] is True
    assert result['reason'] == 'Paper execution failed safely'
    assert '/private/' not in result['reason']


def test_readiness_reports_database_failure_and_secret_store_refuses_plaintext(isolated_runtime, monkeypatch):
    with TestClient(create_app()) as client:
        monkeypatch.setattr('backend.main._database_ok', lambda: False)
        response = client.get('/ready')
        assert response.status_code == 503
        assert response.json()['database'] == 'unavailable'

    with pytest.raises(SecretStorageUnavailable):
        DisabledSecretStore().store('broker-password', 'not-accepted')
