"""Paper trading broker simulation."""
import uuid
from typing import Dict, Optional
from datetime import datetime
from backend.paper_trading.paper_db import (
    init_paper_db, insert_paper_order, update_paper_order_status,
    insert_paper_trade, get_paper_portfolio, get_paper_position,
    apply_paper_fill, cancel_paper_order,
)


class PaperBroker:
    """Simulated paper broker with realistic fills, commissions, slippage."""
    
    def __init__(self, initial_cash: float = 100000.0, commission_rate: float = 0.001,
                 slippage_pct: float = 0.01, db_path: Optional[str] = None):
        init_paper_db(db_path, initial_cash=initial_cash)
        self.db_path = db_path
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.slippage_pct = slippage_pct

    def submit_market_order(self, symbol: str, qty: float, side: str,
                           current_price: float, correlation_id: Optional[str] = None) -> Dict:
        """Submit market order."""
        if qty <= 0 or side.lower() not in {'buy', 'sell'}:
            return {'rejected': True, 'reason': 'Order must have a positive quantity and buy or sell side'}

        portfolio = get_paper_portfolio(self.db_path)
        if not portfolio:
            return {'rejected': True, 'reason': 'Paper portfolio is not initialized'}

        order_id = str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Calculate fill details
        slippage = current_price * (self.slippage_pct / 100.0)
        fill_price = current_price + slippage if side.lower() == 'buy' else current_price - slippage
        commission = abs(qty) * fill_price * self.commission_rate
        total_cost = qty * fill_price + commission

        if side.lower() == 'buy' and portfolio['current_cash'] < total_cost:
            return {'rejected': True, 'reason': 'Insufficient paper cash'}

        if side.lower() == 'sell':
            position = get_paper_position(symbol, self.db_path)
            if not position or position['qty'] < qty:
                return {'rejected': True, 'reason': 'Insufficient paper position to sell'}
        
        # Create order record
        order = {
            'id': order_id,
            'symbol': symbol,
            'qty': qty,
            'side': side,
            'order_type': 'market',
            'price': fill_price,
            'stop_price': None,
            'correlation_id': correlation_id
        }
        insert_paper_order(order, self.db_path)
        
        # Simulate immediate fill
        update_paper_order_status(order_id, 'filled', qty, fill_price, self.db_path)
        
        portfolio_update = apply_paper_fill(
            symbol, qty, side, fill_price, commission, abs(qty) * slippage, self.db_path
        )

        # Create trade record
        trade = {
            'id': str(uuid.uuid4()),
            'order_id': order_id,
            'symbol': symbol,
            'qty': qty,
            'side': side,
            'entry_price': fill_price,
            'exit_price': None,
            'commission': commission,
            'slippage': abs(qty) * slippage,
            'pnl': portfolio_update['realised_pnl'],
            'correlation_id': correlation_id
        }
        insert_paper_trade(trade, self.db_path)
        
        return {
            'order': order,
            'trade': trade,
            'fill_price': fill_price,
            'commission': commission,
            'portfolio': portfolio_update,
        }

    def submit_limit_order(self, symbol: str, qty: float, side: str,
                          limit_price: float, correlation_id: Optional[str] = None) -> Dict:
        """Submit limit order (stored for later trigger)."""
        order_id = str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())
        
        order = {
            'id': order_id,
            'symbol': symbol,
            'qty': qty,
            'side': side,
            'order_type': 'limit',
            'price': limit_price,
            'stop_price': None,
            'correlation_id': correlation_id
        }
        insert_paper_order(order, self.db_path)
        update_paper_order_status(order_id, 'pending', self.db_path)
        
        return {'order': order, 'status': 'pending'}

    def submit_stop_order(self, symbol: str, qty: float, side: str,
                         stop_price: float, correlation_id: Optional[str] = None) -> Dict:
        """Submit stop order."""
        order_id = str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())
        
        order = {
            'id': order_id,
            'symbol': symbol,
            'qty': qty,
            'side': side,
            'order_type': 'stop',
            'price': None,
            'stop_price': stop_price,
            'correlation_id': correlation_id
        }
        insert_paper_order(order, self.db_path)
        update_paper_order_status(order_id, 'pending', self.db_path)
        
        return {'order': order, 'status': 'pending'}

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        return cancel_paper_order(order_id, self.db_path)
