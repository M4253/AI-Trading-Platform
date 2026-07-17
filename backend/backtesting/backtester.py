import uuid
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from dataclasses import dataclass, field

from backend.backtesting.data_provider import DataProvider, HistoricalBar
from backend.backtesting.market_regimes import RegimeType, RegimeDefinition
from backend.backtesting.backtest_db import (
    init_backtest_db, insert_backtest_run, insert_backtest_results, insert_backtest_trade
)
from backend.broker.broker_service import BrokerService
from backend.config.settings import settings


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    entry_date: datetime


@dataclass
class Trade:
    trade_id: str
    symbol: str
    qty: float
    side: str
    entry_price: float
    entry_date: datetime
    exit_price: Optional[float] = None
    exit_date: Optional[datetime] = None
    realized_pnl: float = 0.0
    commission: float = 0.0
    
    def close(self, exit_price: float, exit_date: datetime, commission: float):
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.commission = commission
        if self.side.lower() == 'buy':
            self.realized_pnl = (exit_price - self.entry_price) * self.qty - commission
        else:
            self.realized_pnl = (self.entry_price - exit_price) * self.qty - commission


@dataclass
class BacktestConfig:
    strategy_name: str
    strategy_version: str
    data_provider: DataProvider
    start_date: datetime
    end_date: datetime
    in_sample_ratio: float = 0.7
    initial_cash: float = 100000.0
    commission_rate: float = 0.001
    slippage_pct: float = 0.01
    seed: int = 42
    symbols: List[str] = field(default_factory=list)


class BacktestPortfolio:
    def __init__(self, initial_cash: float, commission_rate: float, slippage_pct: float):
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.commission_rate = commission_rate
        self.slippage_pct = slippage_pct
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.drawdown_series: List[Tuple[datetime, float]] = []
        self.realized_pnl = 0.0
        self.total_commission = 0.0
        self.total_spread_costs = 0.0
        self.total_slippage_costs = 0.0

    def calculate_slippage(self, price: float, is_buy: bool) -> float:
        """Return the slippage cost per share."""
        spread_cost_per_share = price * (self.slippage_pct / 100.0) / 2
        return spread_cost_per_share

    def submit_order(self, symbol: str, qty: float, side: str, current_price: float, timestamp: datetime) -> Optional[Trade]:
        """Execute order if cash/margin allows. Return filled Trade or None if rejected."""
        slippage_per_share = self.calculate_slippage(current_price, side.lower() == 'buy')
        commission = abs(qty) * current_price * self.commission_rate
        self.total_commission += commission
        self.total_slippage_costs += abs(qty) * slippage_per_share

        if side.lower() == 'buy':
            fill_price = current_price + slippage_per_share
            cost = qty * fill_price + commission
            if self.cash < cost:
                return None  # Rejected: insufficient cash
            self.cash -= cost
            if symbol in self.positions:
                pos = self.positions[symbol]
                total_cost = pos.qty * pos.avg_entry_price + qty * fill_price
                pos.qty += qty
                pos.avg_entry_price = total_cost / pos.qty
            else:
                self.positions[symbol] = Position(symbol, qty, fill_price, timestamp)
        else:  # sell
            if symbol not in self.positions or self.positions[symbol].qty < qty:
                return None  # Rejected: no position or insufficient quantity
            fill_price = current_price - slippage_per_share
            proceeds = qty * fill_price - commission
            self.cash += proceeds
            pos = self.positions[symbol]
            pos.qty -= qty

        trade = Trade(
            trade_id=str(uuid.uuid4()),
            symbol=symbol,
            qty=qty,
            side=side,
            entry_price=fill_price if side.lower() == 'buy' else current_price,
            entry_date=timestamp,
            commission=commission
        )
        self.trades.append(trade)
        return trade

    def close_position(self, symbol: str, exit_price: float, exit_date: datetime):
        """Close all shares of a position at exit_price."""
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]
        qty = pos.qty
        if qty > 0:
            commission = qty * exit_price * self.commission_rate
            proceeds = qty * exit_price - commission
            self.cash += proceeds
            pnl = (exit_price - pos.avg_entry_price) * qty - commission
            self.realized_pnl += pnl
            self.total_commission += commission
            del self.positions[symbol]

    def get_total_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio equity = cash + unrealized position values."""
        unrealized = sum(pos.qty * current_prices.get(pos.symbol, pos.avg_entry_price) 
                         for pos in self.positions.values())
        return self.cash + unrealized

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """Sum unrealized P&L across all positions."""
        unrealized_pnl = 0.0
        for pos in self.positions.values():
            current_price = current_prices.get(pos.symbol, pos.avg_entry_price)
            unrealized_pnl += (current_price - pos.avg_entry_price) * pos.qty
        return unrealized_pnl


class Backtester:
    def __init__(self, config: BacktestConfig, db_path: Optional[str] = None):
        self.config = config
        self.db_path = db_path
        init_backtest_db(db_path)
        self.backtest_id = str(uuid.uuid4())
        self.portfolio = BacktestPortfolio(config.initial_cash, config.commission_rate, config.slippage_pct)
        random.seed(config.seed)
        np.random.seed(config.seed)

    def run(self, strategy_fn) -> Dict:
        """Execute backtest with strategy_fn(bars_dict, portfolio) -> signals."""
        insert_backtest_run(
            self.backtest_id, self.config.strategy_name, self.config.strategy_version,
            self.config.start_date.isoformat(), self.config.end_date.isoformat(),
            self.config.in_sample_ratio, self.config.initial_cash,
            self.config.commission_rate, self.config.slippage_pct, self.config.seed, self.db_path
        )

        # Load bars for all symbols
        bars_dict: Dict[str, List[HistoricalBar]] = {}
        for symbol in self.config.symbols:
            bars = self.config.data_provider.get_bars(symbol, self.config.start_date, self.config.end_date)
            bars_dict[symbol] = bars

        if not any(bars_dict.values()):
            return {'error': 'No data loaded for backtest'}

        # Determine dates
        all_dates = set()
        for bars in bars_dict.values():
            for bar in bars:
                all_dates.add(bar.timestamp.date())
        all_dates = sorted(all_dates)

        # Walk-forward split
        split_idx = int(len(all_dates) * self.config.in_sample_ratio)
        in_sample_dates = all_dates[:split_idx]
        out_of_sample_dates = all_dates[split_idx:]

        # Build bar index for fast lookup
        bar_index: Dict[str, Dict[str, HistoricalBar]] = {}
        for symbol, bars in bars_dict.items():
            bar_index[symbol] = {bar.timestamp.date(): bar for bar in bars}

        # Simulate day-by-day
        regime_results: Dict[str, Dict] = {}
        for date in all_dates:
            is_in_sample = date in in_sample_dates
            
            # Get current bars
            current_bars = {}
            current_prices = {}
            for symbol in self.config.symbols:
                bar = bar_index.get(symbol, {}).get(date)
                if bar:
                    current_bars[symbol] = bar
                    current_prices[symbol] = bar.close
                    regime_type = bar.regime
                else:
                    current_prices[symbol] = self.portfolio.positions.get(symbol, {}).avg_entry_price or 100.0

            # Call strategy for signals
            signals = strategy_fn(current_bars, self.portfolio)

            # Process signals
            for signal in signals or []:
                symbol = signal.get('symbol')
                qty = float(signal.get('qty', 0))
                side = signal.get('side', 'buy')
                if symbol in current_prices and qty > 0:
                    price = current_prices[symbol]
                    trade = self.portfolio.submit_order(symbol, qty, side, price, datetime.combine(date, datetime.min.time()))
                    if trade:
                        insert_backtest_trade(
                            trade.trade_id, self.backtest_id, symbol,
                            trade.entry_date.isoformat(), trade.entry_price,
                            '', 0.0, trade.qty, trade.side, 0.0, trade.commission, self.db_path
                        )
                        # Track by regime
                        regime = current_bars.get(symbol, {}).regime if symbol in current_bars else 'neutral'
                        if regime not in regime_results:
                            regime_results[regime] = {'trades': 0, 'wins': 0, 'total_pnl': 0}
                        regime_results[regime]['trades'] += 1

            # Record equity
            equity = self.portfolio.get_total_equity(current_prices)
            self.portfolio.equity_curve.append((datetime.combine(date, datetime.min.time()), equity))

        # Calculate results
        results = self._calculate_results()
        results['regime_breakdown'] = regime_results
        insert_backtest_results(self.backtest_id, results, self.db_path)
        return results

    def _calculate_results(self) -> Dict:
        """Calculate performance metrics."""
        if not self.portfolio.equity_curve:
            return {'error': 'No equity curve data'}

        equity_values = [eq for _, eq in self.portfolio.equity_curve]
        equity_dates = [d for d, _ in self.portfolio.equity_curve]
        initial_cash = self.config.initial_cash

        # Basic metrics
        final_equity = equity_values[-1]
        total_return = (final_equity - initial_cash) / initial_cash
        num_trades = len(self.portfolio.trades)
        closed_trades = [t for t in self.portfolio.trades if t.exit_price is not None]
        num_closed = len(closed_trades)

        # Win rate
        wins = len([t for t in closed_trades if t.realized_pnl > 0])
        win_rate = wins / num_closed if num_closed > 0 else 0.0

        # Average win/loss
        winning_trades = [t.realized_pnl for t in closed_trades if t.realized_pnl > 0]
        losing_trades = [t.realized_pnl for t in closed_trades if t.realized_pnl < 0]
        avg_win = np.mean(winning_trades) if winning_trades else 0.0
        avg_loss = np.mean(losing_trades) if losing_trades else 0.0

        # Profit factor
        gross_profit = sum(winning_trades) if winning_trades else 0.0
        gross_loss = abs(sum(losing_trades)) if losing_trades else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # Drawdown
        cumulative_max = np.maximum.accumulate(equity_values)
        drawdown = (np.array(equity_values) - cumulative_max) / cumulative_max
        max_drawdown = np.min(drawdown)

        # Volatility
        returns = np.diff(equity_values) / np.array(equity_values[:-1])
        volatility = np.std(returns) * np.sqrt(252)

        # Sharpe (risk-free rate = 0)
        sharpe = np.mean(returns) / volatility * np.sqrt(252) if volatility > 0 else 0.0
        
        # Multiple Testing Correction (Bonferroni-like adjustment)
        num_params = 5  # rough estimate of parameters optimized
        adjusted_sharpe = sharpe / np.sqrt(num_params) if num_params > 0 else sharpe

        # Sortino (downside deviation only)
        downside_returns = np.minimum(returns, 0)
        downside_dev = np.std(downside_returns) * np.sqrt(252)
        sortino = np.mean(returns) / downside_dev * np.sqrt(252) if downside_dev > 0 else 0.0

        # Annualized return
        days_traded = len(equity_dates)
        years = days_traded / 252.0
        annualized_return = (final_equity / initial_cash) ** (1 / years) - 1 if years > 0 else total_return

        # Exposure (days with positions / total days)
        days_with_pos = sum(1 for date, _ in self.portfolio.equity_curve if any(self.portfolio.positions.values()))
        exposure = days_with_pos / len(self.portfolio.equity_curve) if self.portfolio.equity_curve else 0.0

        # Turnover (sum of |trades| / avg equity)
        turnover = sum(t.qty for t in self.portfolio.trades) / (np.mean(equity_values) or 1.0) if self.portfolio.trades else 0.0

        return {
            'backtest_id': self.backtest_id,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': float(sharpe),
            'adjusted_sharpe': float(adjusted_sharpe),
            'sortino_ratio': float(sortino),
            'max_drawdown': float(max_drawdown),
            'volatility': float(volatility),
            'num_trades': num_trades,
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'final_equity': final_equity,
            'realized_pnl': self.portfolio.realized_pnl,
            'commission_costs': self.portfolio.total_commission,
            'spread_costs': self.portfolio.total_spread_costs,
            'slippage_costs': self.portfolio.total_slippage_costs,
            'exposure_time': exposure,
            'turnover': turnover,
            'equity_curve': [(d.isoformat(), v) for d, v in self.portfolio.equity_curve]
        }

