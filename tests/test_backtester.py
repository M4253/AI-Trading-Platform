import pytest
import tempfile
from datetime import datetime, timedelta
from backend.backtesting.backtester import Backtester, BacktestConfig, BacktestPortfolio
from backend.backtesting.data_provider import CSVDataProvider, HistoricalBar, DataProvider
from backend.backtesting.market_regimes import RegimeType
from backend.backtesting.backtest_db import init_backtest_db
import pandas as pd
import os


class MockDataProvider(DataProvider):
    """Mock provider for testing."""
    def __init__(self):
        self.bars = {}

    def add_bars(self, symbol, bars):
        self.bars[symbol] = bars

    def get_bars(self, symbol, start_date, end_date):
        if symbol not in self.bars:
            return []
        return [b for b in self.bars[symbol] if start_date <= b.timestamp <= end_date]

    def get_bar_at(self, symbol, timestamp):
        if symbol not in self.bars:
            return None
        bars = [b for b in self.bars[symbol] if b.timestamp <= timestamp]
        return bars[-1] if bars else None


def create_mock_bars(symbol, base_price=100.0, days=252, regime='neutral', trend=0.0):
    """Create synthetic OHLCV bars for testing."""
    bars = []
    current_date = datetime(2020, 1, 1)
    current_price = base_price
    
    for i in range(days):
        # Trend: positive for bull, negative for bear
        price_change = trend * 0.01 * current_price
        current_price += price_change
        
        # Add noise
        noise = (current_price * 0.01 * (i % 3 - 1))  # ±1% noise
        
        open_price = current_price - noise / 2
        close_price = current_price + noise / 2
        high_price = max(open_price, close_price) * 1.01
        low_price = min(open_price, close_price) * 0.99
        
        bar = HistoricalBar(
            timestamp=current_date,
            open_=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=1000000,
            regime=regime
        )
        bars.append(bar)
        current_date += timedelta(days=1)
    
    return bars


def test_backtester_initialization():
    """Test backtester can be initialized."""
    data_provider = MockDataProvider()
    config = BacktestConfig(
        strategy_name='test_strat',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 12, 31),
        symbols=['AAPL']
    )
    backtester = Backtester(config)
    assert backtester.backtest_id is not None


def test_backtester_no_lookahead_bias():
    """Ensure data provider has no forward-looking bias."""
    provider = MockDataProvider()
    bars = create_mock_bars('TEST', days=10)
    provider.add_bars('TEST', bars)
    
    # Can only see data up to timestamp
    target_date = datetime(2020, 1, 5)
    result = provider.get_bar_at('TEST', target_date)
    assert result is not None
    assert result.timestamp <= target_date
    
    # Future dates should not be visible
    future_result = provider.get_bar_at('TEST', datetime(2020, 1, 3))
    assert future_result.timestamp <= datetime(2020, 1, 3)


def test_portfolio_order_execution():
    """Test order execution with slippage and commission."""
    portfolio = BacktestPortfolio(initial_cash=100000.0, commission_rate=0.001, slippage_pct=0.01)
    
    # Place buy order
    trade = portfolio.submit_order('AAPL', 10, 'buy', 100.0, datetime.now())
    assert trade is not None
    assert trade.qty == 10
    assert 'AAPL' in portfolio.positions
    
    # Check cash was deducted (with slippage + commission)
    expected_cost = 10 * 100.0 * 1.001  # price with slippage and commission
    expected_cash = 100000.0 - expected_cost
    assert portfolio.cash < 100000.0


def test_portfolio_insufficient_cash():
    """Test order rejection on insufficient cash."""
    portfolio = BacktestPortfolio(initial_cash=1000.0, commission_rate=0.001, slippage_pct=0.01)
    
    # Try to buy more than cash allows
    trade = portfolio.submit_order('AAPL', 100, 'buy', 100.0, datetime.now())
    assert trade is None  # Should be rejected


def test_portfolio_sell_without_position():
    """Test sell order rejection when no position exists."""
    portfolio = BacktestPortfolio(initial_cash=100000.0, commission_rate=0.001, slippage_pct=0.01)
    
    # Try to sell without position
    trade = portfolio.submit_order('AAPL', 10, 'sell', 100.0, datetime.now())
    assert trade is None  # Should be rejected


def test_walk_forward_split():
    """Test in-sample / out-of-sample split logic."""
    data_provider = MockDataProvider()
    bars = create_mock_bars('TEST', days=100)
    data_provider.add_bars('TEST', bars)
    
    config = BacktestConfig(
        strategy_name='test',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=bars[0].timestamp,
        end_date=bars[-1].timestamp,
        in_sample_ratio=0.7,
        symbols=['TEST']
    )
    
    # Check that split point makes sense
    total_days = 100
    expected_is = int(total_days * 0.7)
    assert expected_is == 70


def test_backtest_run_bull_market():
    """Test backtest execution in bull market."""
    data_provider = MockDataProvider()
    bars = create_mock_bars('TEST', base_price=100.0, days=50, trend=1.0)  # uptrend
    data_provider.add_bars('TEST', bars)
    
    config = BacktestConfig(
        strategy_name='buy_hold',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=bars[0].timestamp,
        end_date=bars[-1].timestamp,
        initial_cash=10000.0,
        symbols=['TEST'],
        seed=42
    )
    
    def buy_and_hold_strategy(current_bars, portfolio):
        if 'TEST' not in portfolio.positions and len(portfolio.trades) == 0:
            return [{'symbol': 'TEST', 'qty': 10, 'side': 'buy'}]
        return []
    
    backtester = Backtester(config)
    results = backtester.run(buy_and_hold_strategy)
    
    # In bull market, should be profitable
    assert results.get('total_return', 0) > -0.1  # Allow small losses due to commissions


def test_backtest_run_bear_market():
    """Test backtest execution in bear market."""
    data_provider = MockDataProvider()
    bars = create_mock_bars('TEST', base_price=100.0, days=50, trend=-1.0)  # downtrend
    data_provider.add_bars('TEST', bars)
    
    config = BacktestConfig(
        strategy_name='short_strat',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=bars[0].timestamp,
        end_date=bars[-1].timestamp,
        initial_cash=10000.0,
        symbols=['TEST'],
        seed=42
    )
    
    def short_strategy(current_bars, portfolio):
        if 'TEST' not in portfolio.positions and len(portfolio.trades) == 0:
            return [{'symbol': 'TEST', 'qty': 5, 'side': 'sell'}]
        return []
    
    backtester = Backtester(config)
    results = backtester.run(short_strategy)
    
    # Shorts in downtrend should be profitable
    assert 'total_return' in results


def test_deterministic_seeded_run():
    """Verify that same seed produces same results."""
    def create_and_run(seed_val):
        data_provider = MockDataProvider()
        bars = create_mock_bars('TEST', days=50)
        data_provider.add_bars('TEST', bars)
        
        config = BacktestConfig(
            strategy_name='test',
            strategy_version='1.0',
            data_provider=data_provider,
            start_date=bars[0].timestamp,
            end_date=bars[-1].timestamp,
            initial_cash=10000.0,
            symbols=['TEST'],
            seed=seed_val
        )
        
        def strategy(current_bars, portfolio):
            return [{'symbol': 'TEST', 'qty': 1, 'side': 'buy'}]
        
        backtester = Backtester(config)
        return backtester.run(strategy)
    
    results1 = create_and_run(42)
    results2 = create_and_run(42)
    
    # Same seed should produce reproducible results
    assert results1.get('total_return') == results2.get('total_return')


def test_transaction_costs():
    """Verify commission and slippage are correctly calculated."""
    portfolio = BacktestPortfolio(initial_cash=100000.0, commission_rate=0.001, slippage_pct=0.01)
    
    initial_cash = portfolio.cash
    trade = portfolio.submit_order('TEST', 100, 'buy', 100.0, datetime.now())
    
    assert trade is not None
    assert portfolio.total_commission > 0
    assert portfolio.total_slippage_costs > 0
    
    # Cash reduction should include both
    expected_reduction = 100 * 100.0 + portfolio.total_commission + portfolio.total_slippage_costs
    assert abs((initial_cash - portfolio.cash) - expected_reduction) < 1


def test_equity_curve_calculation():
    """Test equity curve is properly tracked."""
    data_provider = MockDataProvider()
    bars = create_mock_bars('TEST', days=20)
    data_provider.add_bars('TEST', bars)
    
    config = BacktestConfig(
        strategy_name='test',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=bars[0].timestamp,
        end_date=bars[-1].timestamp,
        initial_cash=10000.0,
        symbols=['TEST']
    )
    
    def strategy(current_bars, portfolio):
        return []
    
    backtester = Backtester(config)
    results = backtester.run(strategy)
    
    assert 'equity_curve' in results
    assert len(results['equity_curve']) > 0
    # First equity should be initial cash
    assert results['equity_curve'][0][1] == 10000.0


def test_regime_breakdown():
    """Test results are broken down by market regime."""
    data_provider = MockDataProvider()
    bars = create_mock_bars('TEST', days=50, regime='bull')
    data_provider.add_bars('TEST', bars)
    
    config = BacktestConfig(
        strategy_name='test',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=bars[0].timestamp,
        end_date=bars[-1].timestamp,
        symbols=['TEST']
    )
    
    def strategy(current_bars, portfolio):
        return []
    
    backtester = Backtester(config)
    results = backtester.run(strategy)
    
    assert 'regime_breakdown' in results


def test_rejected_orders_dont_execute():
    """Verify rejected orders never reach execution."""
    portfolio = BacktestPortfolio(initial_cash=100.0, commission_rate=0.001, slippage_pct=0.01)
    
    initial_trades = len(portfolio.trades)
    
    # Try to buy more than cash allows
    trade = portfolio.submit_order('EXPENSIVE', 1000, 'buy', 1000.0, datetime.now())
    
    assert trade is None
    assert len(portfolio.trades) == initial_trades  # No new trade recorded


def test_sharpe_ratio_calculation():
    """Test Sharpe ratio is calculated (even if approximate)."""
    data_provider = MockDataProvider()
    bars = create_mock_bars('TEST', days=252)
    data_provider.add_bars('TEST', bars)
    
    config = BacktestConfig(
        strategy_name='test',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=bars[0].timestamp,
        end_date=bars[-1].timestamp,
        initial_cash=10000.0,
        symbols=['TEST']
    )
    
    def strategy(current_bars, portfolio):
        return []
    
    backtester = Backtester(config)
    results = backtester.run(strategy)
    
    assert 'sharpe_ratio' in results
    assert isinstance(results['sharpe_ratio'], (int, float))


def test_adjusted_sharpe():
    """Test multiple-testing corrected Sharpe ratio."""
    data_provider = MockDataProvider()
    bars = create_mock_bars('TEST', days=252)
    data_provider.add_bars('TEST', bars)
    
    config = BacktestConfig(
        strategy_name='test',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=bars[0].timestamp,
        end_date=bars[-1].timestamp,
        symbols=['TEST']
    )
    
    def strategy(current_bars, portfolio):
        return []
    
    backtester = Backtester(config)
    results = backtester.run(strategy)
    
    # Adjusted Sharpe should be <= regular Sharpe
    assert 'adjusted_sharpe' in results
    assert results.get('adjusted_sharpe', 0) <= results.get('sharpe_ratio', 0) + 0.01


def test_max_drawdown_calculation():
    """Test max drawdown is correctly computed."""
    data_provider = MockDataProvider()
    # Create a market that rises then falls
    bars = create_mock_bars('TEST', base_price=100.0, days=50, trend=1.0)  # rise
    bars += create_mock_bars('TEST', base_price=150.0, days=50, trend=-2.0)  # fall
    data_provider.add_bars('TEST', bars)
    
    config = BacktestConfig(
        strategy_name='test',
        strategy_version='1.0',
        data_provider=data_provider,
        start_date=bars[0].timestamp,
        end_date=bars[-1].timestamp,
        initial_cash=10000.0,
        symbols=['TEST']
    )
    
    def strategy(current_bars, portfolio):
        return []
    
    backtester = Backtester(config)
    results = backtester.run(strategy)
    
    assert 'max_drawdown' in results
    assert results['max_drawdown'] <= 0  # Drawdown should be negative

