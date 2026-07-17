"""Tests for paper trading engine."""
import pytest
import tempfile
from backend.paper_trading.paper_broker import PaperBroker
from backend.paper_trading.paper_engine import PaperTradingEngine
from backend.paper_trading.paper_db import init_paper_db, get_paper_portfolio, get_paper_orders
import os


@pytest.fixture
def temp_db():
    """Temporary database for tests."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    init_paper_db(db_path)
    yield db_path
    try:
        os.remove(db_path)
    except:
        pass


@pytest.fixture
def paper_broker(temp_db):
    """Create paper broker for testing."""
    return PaperBroker(initial_cash=100000.0, db_path=temp_db)


@pytest.fixture
def paper_engine(temp_db):
    """Create paper trading engine."""
    return PaperTradingEngine(db_path=temp_db)


def test_paper_broker_initialization(paper_broker):
    """Test broker can be initialized."""
    assert paper_broker.initial_cash == 100000.0
    assert paper_broker.commission_rate == 0.001


def test_submit_market_order(paper_broker):
    """Test submitting a market order."""
    result = paper_broker.submit_market_order('AAPL', 10, 'buy', 150.0)
    assert 'order' in result
    assert 'trade' in result
    assert result['order']['symbol'] == 'AAPL'


def test_order_fills_immediately(paper_broker):
    """Test market order fills immediately."""
    result = paper_broker.submit_market_order('AAPL', 10, 'buy', 150.0)
    assert result['order']['id'] is not None


def test_commission_calculated(paper_broker):
    """Test commission is calculated."""
    result = paper_broker.submit_market_order('AAPL', 10, 'buy', 150.0)
    commission = result['commission']
    assert commission > 0
    # 10 * 150 * 0.001 = 1.5
    assert 1.4 < commission < 1.6


def test_slippage_applied(paper_broker):
    """Test slippage is applied to fill price."""
    result = paper_broker.submit_market_order('AAPL', 10, 'buy', 150.0)
    fill_price = result['fill_price']
    # For buy, slippage adds to price
    assert fill_price > 150.0


def test_cancel_order(paper_broker):
    """Test canceling a pending order."""
    result = paper_broker.submit_limit_order('AAPL', 10, 'buy', 145.0)
    order_id = result['order']['id']
    success = paper_broker.cancel_order(order_id)
    assert success


def test_paper_engine_start_trading(paper_engine):
    """Test starting paper trading."""
    paper_engine.start_trading()
    # Should not raise


def test_paper_engine_stop_all_trading(paper_engine):
    """Test emergency stop."""
    paper_engine.stop_all_trading()
    # Subsequent trades should be blocked
    result = paper_engine.execute_trade(
        'AAPL', 10, 'buy',
        {'close': 150.0},
        {'total_equity': 100000.0}
    )
    assert result.get('rejected') == True


def test_execute_trade_through_pipeline(paper_engine):
    """Test full trade execution pipeline."""
    portfolio = get_paper_portfolio(paper_engine.db_path)
    result = paper_engine.execute_trade(
        'AAPL', 10, 'buy',
        {'open': 150.0, 'high': 152.0, 'low': 149.0, 'close': 151.0, 'volatility': 0.02},
        {'total_equity': portfolio['total_equity']},
        'bull'
    )
    assert 'order' in result or 'rejected' in result


def test_risk_validation_blocks_large_order(paper_engine):
    """Test risk manager rejects oversized orders."""
    portfolio = get_paper_portfolio(paper_engine.db_path)
    # Try to buy way too much (should be blocked)
    result = paper_engine.execute_trade(
        'AAPL', 10000, 'buy',  # Huge quantity
        {'close': 150.0},
        {'total_equity': portfolio['total_equity']},
        'neutral'
    )
    assert result.get('rejected') == True


def test_guardrail_monitoring(paper_engine):
    """Test guardrail monitoring doesn't crash."""
    paper_engine.monitor_guardrails()
    # Should not raise


def test_portfolio_metrics_update(paper_engine):
    """Test portfolio metrics can be updated."""
    paper_engine.update_portfolio_metrics()
    # Should not raise


def test_orders_persisted(paper_engine, temp_db):
    """Test orders are persisted to database."""
    paper_engine.execute_trade(
        'TEST', 5, 'buy',
        {'close': 100.0},
        {'total_equity': 100000.0}
    )
    orders = get_paper_orders(db_path=temp_db)
    assert len(orders) > 0

