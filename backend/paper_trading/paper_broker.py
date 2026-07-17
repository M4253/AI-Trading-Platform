"""Paper trading broker simulation."""
import uuid
from typing import Dict, Optional
from datetime import datetime
from backend.paper_trading.paper_db import (
    init_paper_db, insert_paper_order, update_paper_order_status,
    insert_paper_trade, get_paper_portfolio, update_paper_portfolio,
    set_paper_trading_state, get_paper_trading_state
)


class PaperBroker:
    """Simulated paper broker with realistic fills, commissions, slippage."""
    
    def __init__(self, initial_cash: float = 100000.0, commission_rate: float = 0.001,
                 slippage_pct: float = 0.01, db_path: Optional[str] = None):
        init_paper_db(db_path)
        self.db_path = db_path
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.slippage_pct = slippage_pct

    def submit_market_order(self, symbol: str, qty: float, side: str,
                           current_price: float, correlation_id: Optional[str] = None) -> Dict:
        """Submit market order."""
        order_id = str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Calculate fill details
        slippage = current_price * (self.slippage_pct / 100.0)
        fill_price = current_price + slippage if side.lower() == 'buy' else current_price - slippage
        commission = abs(qty) * fill_price * self.commission_rate
        
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
            'correlation_id': correlation_id
        }
        insert_paper_trade(trade, self.db_path)
        
        # Update portfolio
        portfolio = get_paper_portfolio(self.db_path)
        if portfolio:
            if side.lower() == 'buy':
                new_cash = portfolio['current_cash'] - (qty * fill_price + commission)
            else:
                new_cash = portfolio['current_cash'] + (qty * fill_price - commission)
            
            update_paper_portfolio({
                'current_cash': new_cash,
                'commission_costs': portfolio['commission_costs'] + commission
            }, self.db_path)
        
        return {
            'order': order,
            'trade': trade,
            'fill_price': fill_price,
            'commission': commission
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
        update_paper_order_status(order_id, 'cancelled', self.db_path)
        return True

