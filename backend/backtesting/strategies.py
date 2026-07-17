"""Example strategies for backtesting."""
from typing import List, Dict, Optional


def simple_momentum_strategy(current_bars: Dict, portfolio) -> List[Dict]:
    """
    Simple momentum strategy: buy on up days, sell on down days.
    No lookahead - only uses current bar data.
    """
    signals = []
    for symbol, bar in current_bars.items():
        if bar.close > bar.open:  # Up day
            # Check if already long
            if symbol not in portfolio.positions:
                signals.append({'symbol': symbol, 'qty': 10, 'side': 'buy'})
        else:  # Down day
            # Close existing positions
            if symbol in portfolio.positions:
                pos_qty = portfolio.positions[symbol].qty
                if pos_qty > 0:
                    signals.append({'symbol': symbol, 'qty': pos_qty, 'side': 'sell'})
    return signals


def mean_reversion_strategy(current_bars: Dict, portfolio) -> List[Dict]:
    """
    Mean reversion: buy on low close, sell on high close.
    Uses only point-in-time data.
    """
    signals = []
    for symbol, bar in current_bars.items():
        # Simple heuristic: if price is 2% below open, buy
        if bar.close < bar.open * 0.98 and symbol not in portfolio.positions:
            signals.append({'symbol': symbol, 'qty': 5, 'side': 'buy'})
        # If price is 2% above open, sell
        elif bar.close > bar.open * 1.02 and symbol in portfolio.positions:
            pos_qty = portfolio.positions[symbol].qty
            if pos_qty > 0:
                signals.append({'symbol': symbol, 'qty': pos_qty, 'side': 'sell'})
    return signals


def buy_and_hold_strategy(current_bars: Dict, portfolio) -> List[Dict]:
    """
    Buy and hold: buy once and hold forever.
    Tests baseline performance.
    """
    signals = []
    # Only buy once (first signal of backtest)
    if len(portfolio.trades) == 0:
        for symbol in current_bars.keys():
            signals.append({'symbol': symbol, 'qty': 10, 'side': 'buy'})
    return signals

