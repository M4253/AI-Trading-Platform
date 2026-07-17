import pytest
from backend.broker import broker_service


def test_simulated_broker_submit_and_cancel(tmp_path, monkeypatch):
    # Ensure LIVE_TRADING is False for this test
    monkeypatch.setattr('backend.config.settings.settings.LIVE_TRADING', False)
    svc = broker_service.BrokerService(db_path=str(tmp_path / 'test.db'))
    res = svc.submit_order('TEST', 2, 'buy')
    assert 'order' in res and 'trade' in res
    order_id = res['order']['id']
    # Cancel should fail because filled
    assert not svc.cancel_order(order_id)


def test_ibkr_broker_stays_disconnected_and_rejects_execution(tmp_path):
    """No test may turn a local mock into a simulated live-broker approval."""
    from backend.broker.ibkr_broker import IBKRBroker

    broker = IBKRBroker(
        db_path=str(tmp_path / 'ib.db'),
        paper=False,
        host='127.0.0.1',
        port=7496,
    )

    assert broker.paper is True
    assert broker.connect() is False
    with pytest.raises(RuntimeError, match='IBKR order execution is disabled'):
        broker.submit_order('MOCK', 1, 'buy', order_type='limit', price=123.45)
