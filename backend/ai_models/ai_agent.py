"""
AI Trading Agent that generates trade proposals with reasoning.
All trades flow through Decision Engine and Risk Manager before execution.
"""
import uuid
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import json

from backend.ai_models.ai_decision_engine import decide_and_execute
from backend.risk_engine.risk_manager import RiskManager
from backend.db.ai_db import init_ai_db, insert_ai_decision, update_ai_decision_status, insert_ai_decision_input


class TradingAnalysis:
    """Represents AI analysis result."""
    def __init__(self, symbol: str, opportunity_score: float, confidence_score: float, 
                 risk_score: float, rationale: str, inputs: Dict):
        self.symbol = symbol
        self.opportunity_score = opportunity_score  # 0-100
        self.confidence_score = confidence_score    # 0-100
        self.risk_score = risk_score                # 0-100
        self.rationale = rationale
        self.inputs = inputs
        self.action = None
        self.qty = None
        self.side = None
        self.expected_reward = None
        self.risk_level = None


class AIAgent:
    """AI Trading Agent that analyzes opportunities and proposes trades."""
    
    def __init__(self, model_name: str = 'claude-haiku', model_version: str = '1.0', 
                 prompt_version: str = '1.0', db_path: Optional[str] = None):
        init_ai_db(db_path)
        self.db_path = db_path
        self.model_name = model_name
        self.model_version = model_version
        self.prompt_version = prompt_version
        self.risk_manager = RiskManager()

    def analyze_opportunity(self, symbol: str, current_price: float, market_data: Dict,
                           portfolio_state: Dict, market_regime: str,
                           fundamentals: Optional[Dict] = None,
                           sentiment: Optional[Dict] = None,
                           macro_data: Optional[Dict] = None) -> TradingAnalysis:
        """
        Analyze trade opportunity using multiple data sources.
        Returns TradingAnalysis with scores and rationale.
        """
        inputs = {
            'symbol': symbol,
            'current_price': current_price,
            'market_regime': market_regime,
            'portfolio_state': portfolio_state,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Extract key metrics from market data
        if market_data:
            inputs['market_data'] = {k: v for k, v in market_data.items() if isinstance(v, (int, float, str))}

        # Analyze trend
        price_trend = self._analyze_trend(market_data)  # -1 to +1
        volatility = market_data.get('volatility', 0.0) if market_data else 0.0
        
        # Analyze sentiment if available
        sentiment_score = 0.5
        if sentiment:
            sentiment_score = sentiment.get('overall_sentiment', 0.5)
            inputs['sentiment'] = sentiment_score

        # Analyze fundamentals if available
        value_score = 0.5
        if fundamentals:
            pe_ratio = fundamentals.get('pe_ratio', 0)
            if pe_ratio and pe_ratio < 15:
                value_score = 0.7
            inputs['fundamentals'] = {'pe_ratio': pe_ratio}

        # Market regime impact
        regime_bias = {'bull': 0.3, 'bear': -0.3, 'sideways': 0.0, 
                       'crash': -0.5, 'high_vol': -0.2, 'low_vol': 0.1}.get(market_regime, 0.0)

        # Composite opportunity score
        opportunity_score = (
            (price_trend * 0.4 + 0.5) * 50 +  # Trend component
            (sentiment_score * 0.3) * 50 +      # Sentiment
            (value_score * 0.2) * 50 +          # Value
            (regime_bias * 0.1 + 0.5) * 50      # Regime
        )
        opportunity_score = max(0, min(100, opportunity_score))

        # Confidence based on data completeness and agreement
        data_completeness = sum([bool(market_data), bool(fundamentals), bool(sentiment), bool(macro_data)]) / 4.0
        confidence_score = (data_completeness * 0.5 + 0.5) * 100

        # Risk score based on volatility and position size
        portfolio_equity = portfolio_state.get('total_equity', 100000.0)
        position_value = current_price * 10  # Assume 10 shares
        position_ratio = position_value / portfolio_equity
        risk_score = (volatility * 0.5 + position_ratio * 0.5) * 100
        risk_score = max(0, min(100, risk_score))

        # Generate detailed rationale
        rationale = self._generate_rationale(
            symbol, price_trend, sentiment_score, value_score, 
            market_regime, confidence_score, risk_score,
            current_price, volatility
        )

        analysis = TradingAnalysis(
            symbol=symbol,
            opportunity_score=opportunity_score,
            confidence_score=confidence_score,
            risk_score=risk_score,
            rationale=rationale,
            inputs=inputs
        )

        return analysis

    def _analyze_trend(self, market_data: Optional[Dict]) -> float:
        """Analyze price trend. Returns -1 (down) to +1 (up)."""
        if not market_data:
            return 0.0
        
        close = market_data.get('close', 0.0)
        open_price = market_data.get('open', 0.0)
        high = market_data.get('high', 0.0)
        low = market_data.get('low', 0.0)

        if close >= open_price:
            return min(1.0, (close - open_price) / (high - low + 0.01))
        else:
            return max(-1.0, -(open_price - close) / (high - low + 0.01))

    def _generate_rationale(self, symbol: str, trend: float, sentiment: float, value: float,
                            regime: str, confidence: float, risk: float,
                            price: float, volatility: float) -> str:
        """Generate human-readable explanation of the analysis."""
        lines = [
            f"ANALYSIS FOR {symbol}",
            f"Current Price: ${price:.2f}",
            "",
            "KEY DRIVERS:",
        ]

        if trend > 0.3:
            lines.append(f"  • Price Momentum: Positive uptrend detected (trend={trend:.2f})")
        elif trend < -0.3:
            lines.append(f"  • Price Momentum: Negative downtrend detected (trend={trend:.2f})")
        else:
            lines.append(f"  • Price Momentum: Neutral/sideways (trend={trend:.2f})")

        if sentiment > 0.6:
            lines.append(f"  • Market Sentiment: Bullish (sentiment score={sentiment:.2f})")
        elif sentiment < 0.4:
            lines.append(f"  • Market Sentiment: Bearish (sentiment score={sentiment:.2f})")
        else:
            lines.append(f"  • Market Sentiment: Mixed (sentiment score={sentiment:.2f})")

        if value > 0.6:
            lines.append(f"  • Valuation: Attractively valued (value score={value:.2f})")
        else:
            lines.append(f"  • Valuation: Fair to expensive (value score={value:.2f})")

        lines.extend([
            f"  • Market Regime: {regime.upper()}",
            f"  • Volatility: {volatility:.2%}",
            "",
            "ASSESSMENT:",
            f"  Confidence: {confidence:.1f}% - Data quality and signal agreement",
            f"  Risk Level: {risk:.1f}% - Based on volatility and position sizing",
            "",
            "RECOMMENDATION:",
        ])

        if confidence > 70 and risk < 50:
            lines.append("  ACTION: BUY SIGNAL")
            lines.append("  RATIONALE: High conviction, favorable risk/reward")
        elif confidence > 60 and risk < 60:
            lines.append("  ACTION: BUY SIGNAL (Moderate)")
            lines.append("  RATIONALE: Decent conviction with manageable risk")
        elif confidence > 70 and trend < -0.2:
            lines.append("  ACTION: SELL/SHORT SIGNAL")
            lines.append("  RATIONALE: High confidence in downside move")
        else:
            lines.append("  ACTION: HOLD/MONITOR")
            lines.append("  RATIONALE: Insufficient conviction or unfavorable risk/reward")

        lines.extend([
            "",
            "RISK FACTORS:",
            f"  • Market regime is {regime} - may limit upside",
            f"  • Volatility at {volatility:.2%} - can amplify losses",
            "  • Position sizing will be limited by risk management rules",
        ])

        return "\n".join(lines)

    def propose_trade(self, analysis: TradingAnalysis, portfolio_state: Dict,
                      current_prices: Dict) -> Optional[Dict]:
        """
        Convert analysis to trade proposal.
        Returns proposal dict if confidence/opportunity thresholds met, else None.
        """
        # Decision rules
        if analysis.opportunity_score < 50 or analysis.confidence_score < 50:
            return None  # Insufficient signals

        decision_id = str(uuid.uuid4())
        
        # Determine action
        if analysis.opportunity_score > 65 and analysis.confidence_score > 65:
            proposed_action = 'BUY' if analysis.opportunity_score > 50 else 'SELL'
            qty = 10  # Base quantity
        else:
            return None  # No action warranted

        # Calculate risk metrics
        current_price = current_prices.get(analysis.symbol, 100.0)
        entry_price = current_price
        stop_loss = entry_price * 0.95  # 5% stop
        take_profit = entry_price * 1.10  # 10% target
        expected_reward = (take_profit - entry_price) * qty
        risk_amount = (entry_price - stop_loss) * qty
        risk_reward_ratio = expected_reward / (risk_amount + 0.01)

        proposal = {
            'decision_id': decision_id,
            'symbol': analysis.symbol,
            'proposed_action': proposed_action,
            'proposed_side': 'buy' if proposed_action == 'BUY' else 'sell',
            'proposed_qty': qty,
            'confidence_score': analysis.confidence_score,
            'opportunity_score': analysis.opportunity_score,
            'risk_score': analysis.risk_score,
            'expected_reward': expected_reward,
            'risk_reward_ratio': risk_reward_ratio,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'rationale': analysis.rationale,
            'inputs': analysis.inputs,
            'model_name': self.model_name,
            'model_version': self.model_version,
            'prompt_version': self.prompt_version,
            'timestamp': datetime.utcnow().isoformat()
        }

        return proposal

    def execute_proposal(self, proposal: Dict, risk_manager: RiskManager,
                         portfolio_state: Dict, current_prices: Dict) -> Dict:
        """
        Execute trade proposal through full pipeline:
        AI Proposal → Risk Validation → Decision Engine → Execution
        Returns execution result with full audit trail.
        """
        decision_id = proposal['decision_id']
        
        # Store AI decision in DB
        decision_record = {
            'id': decision_id,
            'symbol': proposal['symbol'],
            'proposed_action': proposal['proposed_action'],
            'proposed_qty': proposal['proposed_qty'],
            'proposed_side': proposal['proposed_side'],
            'confidence_score': proposal['confidence_score'],
            'opportunity_score': proposal['opportunity_score'],
            'risk_score': proposal['risk_score'],
            'expected_reward': proposal.get('expected_reward'),
            'risk_reward_ratio': proposal.get('risk_reward_ratio'),
            'rationale': proposal['rationale'],
            'inputs': proposal['inputs'],
            'model_name': proposal['model_name'],
            'model_version': proposal['model_version'],
            'prompt_version': proposal['prompt_version'],
            'timestamp': proposal['timestamp'],
            'decision_status': 'pending',
            'execution_status': 'pending'
        }
        insert_ai_decision(decision_record, self.db_path)

        result = {
            'decision_id': decision_id,
            'proposal': proposal,
            'audit_trail': [],
            'final_execution': None,
            'rejected': False,
            'rejection_reason': None
        }

        # Stage 1: Risk Management validation
        try:
            risk_approval = risk_manager.validate_order(
                portfolio_state,
                {'symbol': proposal['symbol'], 'qty': proposal['proposed_qty'], 'side': proposal['proposed_side']},
                current_prices
            )
            
            if not risk_approval:
                result['rejected'] = True
                result['rejection_reason'] = 'Risk management validation failed'
                result['audit_trail'].append({
                    'stage': 'risk_validation',
                    'passed': False,
                    'reason': 'Position size or leverage exceeds limits'
                })
                update_ai_decision_status(decision_id, 'rejected_by_risk', 'cancelled', None, self.db_path)
                return result

            result['audit_trail'].append({
                'stage': 'risk_validation',
                'passed': True,
                'reason': 'Within risk parameters'
            })
        except Exception as e:
            result['rejected'] = True
            result['rejection_reason'] = f'Risk validation error: {str(e)}'
            update_ai_decision_status(decision_id, 'error', 'failed', None, self.db_path)
            return result

        # Stage 2: Decision Engine approval
        try:
            decision_signal = {
                'symbol': proposal['symbol'],
                'qty': proposal['proposed_qty'],
                'side': proposal['proposed_side'],
                'order_type': 'market',
                'ai_decision_id': decision_id
            }
            
            execution_result = decide_and_execute(decision_signal, db_path=self.db_path)
            
            if execution_result and 'order' in execution_result:
                result['final_execution'] = execution_result
                result['audit_trail'].append({
                    'stage': 'decision_engine_execution',
                    'passed': True,
                    'reason': 'Order placed successfully'
                })
                order_id = execution_result['order'].get('id')
                update_ai_decision_status(decision_id, 'approved', 'executed', order_id, self.db_path)
            else:
                result['rejected'] = True
                result['rejection_reason'] = execution_result.get(
                    'reason', 'Decision engine returned no execution'
                ) if execution_result else 'Decision engine returned no execution'
                result['audit_trail'].append({
                    'stage': 'decision_engine',
                    'passed': False,
                    'reason': result['rejection_reason']
                })
                update_ai_decision_status(decision_id, 'rejected_by_engine', 'cancelled', None, self.db_path)

        except Exception as e:
            result['rejected'] = True
            result['rejection_reason'] = f'Decision engine error: {str(e)}'
            result['audit_trail'].append({
                'stage': 'decision_engine',
                'passed': False,
                'reason': str(e)
            })
            update_ai_decision_status(decision_id, 'error', 'failed', None, self.db_path)

        return result
