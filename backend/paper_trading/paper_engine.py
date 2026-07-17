"""Main paper trading engine orchestrating AI → Risk → Execution."""
from typing import Dict, Optional
from datetime import datetime
from backend.paper_trading.paper_broker import PaperBroker
from backend.paper_trading.paper_db import (
    get_paper_trading_state, set_paper_trading_state, get_paper_portfolio,
    insert_risk_event, update_paper_portfolio
)
from backend.risk_engine.risk_manager import RiskManager
from backend.ai_models.ai_agent import AIAgent
import uuid


class PaperTradingEngine:
    """Orchestrates paper trading with AI, Risk, and Execution."""
    
    def __init__(self, db_path: Optional[str] = None, initial_cash: float = 100000.0):
        self.db_path = db_path
        self.broker = PaperBroker(initial_cash=initial_cash, db_path=db_path)
        self.risk_manager = RiskManager()
        self.ai_agent = AIAgent(db_path=db_path)
        self._trading_halted = False
        self._daily_loss = 0.0
        self._weekly_loss = 0.0
        self.daily_loss_limit = -initial_cash * 0.05  # 5% daily loss limit
        self.weekly_loss_limit = -initial_cash * 0.10  # 10% weekly loss limit

    def start_trading(self):
        """Start paper trading."""
        set_paper_trading_state('status', 'running', self.db_path)
        set_paper_trading_state('trading_halted', 'false', self.db_path)
        self._trading_halted = False

    def pause_trading(self):
        """Pause paper trading."""
        set_paper_trading_state('status', 'paused', self.db_path)

    def resume_trading(self):
        """Resume paper trading."""
        set_paper_trading_state('status', 'running', self.db_path)

    def stop_all_trading(self):
        """Emergency stop all trading."""
        set_paper_trading_state('trading_halted', 'true', self.db_path)
        self._trading_halted = True
        insert_risk_event({
            'event_type': 'halt',
            'severity': 'critical',
            'description': 'Trading halted by manual command',
            'guardrail_name': 'emergency_stop',
            'action_taken': 'all_new_orders_blocked'
        }, self.db_path)

    def execute_trade(self, symbol: str, qty: float, side: str,
                      market_data: Dict, portfolio_state: Dict,
                      market_regime: str = 'neutral') -> Dict:
        """Execute trade through full pipeline: AI → Risk → Execution."""
        correlation_id = str(uuid.uuid4())
        
        # Check if trading is halted
        if self._trading_halted or get_paper_trading_state('trading_halted', self.db_path) == 'true':
            return {
                'rejected': True,
                'reason': 'Trading halted by emergency stop',
                'correlation_id': correlation_id
            }
        
        # AI Analysis
        analysis = self.ai_agent.analyze_opportunity(
            symbol, market_data.get('close', 100.0), market_data,
            portfolio_state, market_regime
        )
        
        # Risk Validation
        if not self.risk_manager.validate_order(portfolio_state, 
                                                 {'symbol': symbol, 'qty': qty, 'side': side},
                                                 {symbol: market_data.get('close', 100.0)}):
            insert_risk_event({
                'event_type': 'order_rejected',
                'severity': 'warning',
                'description': f'Order rejected: {symbol} {qty} {side}',
                'guardrail_name': 'position_size_limit',
                'current_value': qty,
                'action_taken': 'order_blocked'
            }, self.db_path)
            return {
                'rejected': True,
                'reason': 'Risk management validation failed',
                'correlation_id': correlation_id
            }
        
        # Execute via paper broker
        try:
            result = self.broker.submit_market_order(
                symbol, qty, side, market_data.get('close', 100.0), correlation_id
            )
            return {
                'executed': True,
                'order': result['order'],
                'trade': result['trade'],
                'correlation_id': correlation_id
            }
        except Exception as e:
            return {
                'rejected': True,
                'reason': f'Execution error: {str(e)}',
                'correlation_id': correlation_id
            }

    def monitor_guardrails(self):
        """Monitor risk guardrails and take action if breached."""
        portfolio = get_paper_portfolio(self.db_path)
        if not portfolio:
            return
        
        # Check drawdown
        equity_high = portfolio['equity_high_water_mark']
        current_equity = portfolio['total_equity']
        drawdown = (current_equity - equity_high) / (equity_high or 1.0)
        
        if drawdown < -0.10:  # More than 10% drawdown
            self.stop_all_trading()
            insert_risk_event({
                'event_type': 'guardrail_breach',
                'severity': 'critical',
                'description': 'Maximum drawdown exceeded',
                'guardrail_name': 'max_drawdown',
                'current_value': drawdown,
                'threshold': -0.10,
                'action_taken': 'halt_trading'
            }, self.db_path)

    def update_portfolio_metrics(self):
        """Update portfolio equity, P&L, and drawdown."""
        portfolio = get_paper_portfolio(self.db_path)
        if not portfolio:
            return
        
        # Calculate total equity from positions + cash
        total_equity = portfolio['current_cash']
        update_paper_portfolio({
            'total_equity': total_equity,
            'total_unrealised_pnl': 0.0  # Would sum positions here
        }, self.db_path)

