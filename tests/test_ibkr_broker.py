import os
import types
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


class DummyIB:
    def __init__(self):
        self._connected = False
        self._placed = []

    def connect(self, host, port, clientId, timeout=None):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def placeOrder(self, contract, order):
        # create a dummy object with orderStatus
        class OS:
            def __init__(self):
                self.status = 'Filled'
                self.avgFillPrice = getattr(order, 'lmtPrice', None) or 123.45
        class T:
            def __init__(self):
                self.orderStatus = OS()
        return T()

    def positions(self):
        return []

    def accountSummary(self):
        return []

    def sleep(self, sec):
        import time
        time.sleep(0)


def test_ibkr_broker_live_flow(monkeypatch, tmp_path):
    # Force settings to think live trading but monkeypatch IB to DummyIB
    monkeypatch.setattr('backend.config.settings.settings.LIVE_TRADING', True)
    # monkeypatch ib_insync.IB used by IBKRBroker
    dummy_module = types.SimpleNamespace(IB=lambda: DummyIB(), Stock=lambda s, e, c: None, MarketOrder=lambda side, qty: types.SimpleNamespace(), LimitOrder=lambda side, qty, price: types.SimpleNamespace(lmtPrice=price))
    monkeypatch.setitem(__import__('sys').modules, 'ib_insync', dummy_module)
    # reload the IBKRBroker module to pick up the mocked ib_insync
    from importlib import reload
    import backend.broker.ibkr_broker as ibmod
    reload(ibmod)
    broker = ibmod.IBKRBroker(db_path=str(tmp_path / 'ib.db'), paper=False)
    res = broker.submit_order('MOCK', 1, 'buy', order_type='limit', price=123.45)
    assert 'order' in res
    assert res.get('trade') is not None

