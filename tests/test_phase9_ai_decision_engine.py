"""Phase 9 tests for the modular, paper-only AI decision engine."""
import inspect

import pytest
from fastapi.testclient import TestClient

from backend.ai_models import ai_decision_engine
from backend.ai_models.ai_decision_engine import AIDecisionEngine, available_models
from backend.db import db as db_module
from backend.db.ai_db import (
    get_ai_decision,
    get_ai_execution_settings,
    init_ai_db,
    list_ai_decision_audit,
    update_ai_execution_settings,
)
from backend.main import app
from backend.paper_trading.paper_engine import PaperTradingEngine


@pytest.fixture
def decision_db(tmp_path):
    path = str(tmp_path / 'phase9_decisions.db')
    init_ai_db(path)
    return path


@pytest.fixture
def rich_context():
    return {
        'symbol': 'AAPL',
        'current_price': 109.0,
        'market_data': {'open': 100.0, 'high': 110.0, 'low': 99.0, 'close': 109.0, 'volume': 1_500_000, 'volatility': 0.01},
        'chart_data': {'closes': [100.0, 101.0, 102.0, 103.0, 105.0, 106.0, 107.0, 109.0]},
        'indicators': {'rsi': 65.0, 'macd': 0.03},
        'news': [{'headline': 'Company reports record profit growth and receives an upgrade'}],
        'portfolio_state': {'current_cash': 100_000.0, 'total_equity': 100_000.0, 'positions': []},
    }


def test_decision_records_full_context_reasoning_scores_and_audit(decision_db, rich_context):
    engine = AIDecisionEngine(db_path=decision_db)

    decision = engine.create_decision(**rich_context, execution_mode='manual_approval')
    stored = get_ai_decision(decision['id'], decision_db)

    assert decision['model_key'] == 'rule_based_v1'
    assert decision['execution_mode'] == 'manual_approval'
    assert decision['confidence_score'] > 0
    assert decision['rationale']
    assert decision['reasoning']
    assert stored['context']['chart_data'] == rich_context['chart_data']
    assert stored['context']['indicators']['rsi'] == 65.0
    assert stored['context']['news'][0]['headline'].startswith('Company reports')
    assert stored['context']['portfolio_state']['total_equity'] == 100_000.0
    assert len(list_ai_decision_audit(decision['id'], decision_db)) >= 2


def test_manual_approval_executes_only_through_started_paper_engine(decision_db, rich_context):
    PaperTradingEngine(db_path=decision_db).start_trading()
    engine = AIDecisionEngine(db_path=decision_db)

    decision = engine.create_decision(**rich_context, execution_mode='manual_approval')
    assert decision['proposed_action'] == 'BUY'
    assert decision['execution_status'] == 'pending_approval'

    executed = engine.execute_saved_decision(decision['id'])

    assert executed['execution_status'] == 'paper_executed'
    assert executed['outcome'] == 'paper_executed'
    assert executed['final_order_id']
    assert any(entry['stage'] == 'paper_execution' for entry in list_ai_decision_audit(decision['id'], decision_db))


def test_automatic_mode_remains_paper_only_and_records_outcome(decision_db, rich_context):
    PaperTradingEngine(db_path=decision_db).start_trading()
    engine = AIDecisionEngine(db_path=decision_db)

    decision = engine.create_decision(**rich_context, execution_mode='automatic_paper')

    assert decision['execution_mode'] == 'automatic_paper'
    assert decision['execution_status'] == 'paper_executed'
    assert decision['outcome'] == 'paper_executed'
    assert decision['execution_details']['executed'] is True


def test_execution_settings_default_to_manual_and_reject_live_modes(decision_db):
    assert get_ai_execution_settings(decision_db) == {
        'execution_mode': 'manual_approval',
        'model_key': 'rule_based_v1',
        'paper_only': True,
    }
    updated = update_ai_execution_settings(execution_mode='automatic_paper', db_path=decision_db)
    assert updated['execution_mode'] == 'automatic_paper'
    with pytest.raises(ValueError, match='manual_approval or automatic_paper'):
        update_ai_execution_settings(execution_mode='live', db_path=decision_db)
    assert available_models() == [
        {'key': 'rule_based_v1', 'display_name': 'Rule-based paper model', 'version': '1.0'}
    ]


def test_decision_api_uses_saved_policy_and_forbids_credential_fields(monkeypatch, tmp_path, rich_context):
    db_path = str(tmp_path / 'phase9_api.db')
    monkeypatch.setattr(db_module, 'DEFAULT_DB', db_path)
    init_ai_db(db_path)
    PaperTradingEngine(db_path=db_path).start_trading()
    client = TestClient(app)

    assert client.patch('/ai/settings', json={'execution_mode': 'manual_approval'}).json()['paper_only'] is True
    created = client.post('/ai/decisions', json={key: value for key, value in rich_context.items() if key != 'portfolio_state'})
    assert created.status_code == 201
    decision = created.json()
    assert decision['execution_status'] == 'pending_approval'
    assert decision['context']['portfolio_state']['total_equity'] == 100_000.0

    detail = client.get(f"/ai/decisions/{decision['id']}")
    assert detail.status_code == 200
    assert detail.json()['audit_trail']

    approved = client.post(f"/ai/decisions/{decision['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()['execution_status'] == 'paper_executed'

    credentials = client.post('/ai/decisions', json={
        **{key: value for key, value in rich_context.items() if key != 'portfolio_state'},
        'password': 'never-accepted',
    })
    assert credentials.status_code == 422
    nested_credentials = client.post('/ai/decisions', json={
        **{key: value for key, value in rich_context.items() if key != 'portfolio_state'},
        'market_data': {'open': 100, 'close': 109, 'api_key': 'never-stored'},
    })
    assert nested_credentials.status_code == 422


def test_decision_engine_does_not_import_or_name_a_real_broker_client():
    source = inspect.getsource(ai_decision_engine)
    assert 'IBKRBroker' not in source
    assert 'ib_insync' not in source
