from typing import Dict, Optional


class RiskManager:
    def __init__(self, max_position_size: float = 0.1, max_leverage: float = 1.0, stop_loss_pct: float = 0.05):
        self.max_position_size = max_position_size
        self.max_leverage = max_leverage
        self.stop_loss_pct = stop_loss_pct

    def validate_order(self, portfolio: Dict, signal: Dict, current_prices: Dict) -> bool:
        """Check if order passes risk limits. Return True if approved."""
        symbol = signal.get('symbol')
        qty = float(signal.get('qty', 0))
        side = signal.get('side', 'buy')

        if qty <= 0:
            return False
        
        # Simple check: position size limits
        total_equity = portfolio.get('total_equity', 100000.0)
        position_value = qty * current_prices.get(symbol, 100.0)
        if position_value > total_equity * self.max_position_size:
            return False

        return True

    def calculate_position_size(self, account_equity: float, volatility: float) -> float:
        """Return recommended position size based on account equity and volatility."""
        return (account_equity * self.max_position_size) / (volatility + 0.01)

