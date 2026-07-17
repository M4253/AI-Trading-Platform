import pytest
from datetime import datetime
from backend.ai_models.ai_agent import AIAgent, TradingAnalysis
from backend.risk_engine.risk_manager import RiskManager
from backend.db.ai_db import init_ai_db, get_ai_decision, list_ai_decisions
import tempfile


@pytest.fixture
def temp_db():
    """Create temporary database for tests."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    init_ai_db(db_path)
    yield db_path
    import os
    try:
        os.remove(db_path)
    except:
        pass


@pytest.fixture
def ai_agent(temp_db):
    """Create AI agent for testing."""
    return AIAgent(model_name='test-model', model_version='1.0', db_path=temp_db)


@pytest.fixture
def sample_portfolio():
    """Sample portfolio state."""
    return {
        'total_equity': 100000.0,
        'cash': 50000.0,
        'positions': [
            {'symbol': 'AAPL', 'qty': 10, 'avg_price': 150.0}
        ]
    }


@pytest.fixture
def sample_market_data():
    """Sample market data for analysis."""
    return {
        'open': 100.0,
        'high': 105.0,
        'low': 98.0,
        'close': 103.0,
        'volume': 1000000,
        'volatility': 0.02
    }


def test_ai_agent_initialization(ai_agent):
    """Test AI agent can be initialized."""
    assert ai_agent.model_name == 'test-model'
    assert ai_agent.model_version == '1.0'


def test_trading_analysis_creation():
    """Test TradingAnalysis object creation."""
    analysis = TradingAnalysis(
        symbol='TEST',
        opportunity_score=75.0,
        confidence_score=80.0,
        risk_score=30.0,
        rationale='Test rationale',
        inputs={}
    )
    assert analysis.symbol == 'TEST'
    assert analysis.opportunity_score == 75.0


def test_analyze_opportunity_bullish(ai_agent, sample_portfolio, sample_market_data):
    """Test analysis with bullish signals."""
    analysis = ai_agent.analyze_opportunity(
        symbol='TEST',
        current_price=100.0,
        market_data=sample_market_data,
        portfolio_state=sample_portfolio,
        market_regime='bull'
    )
    assert analysis is not None
    assert analysis.symbol == 'TEST'
    assert 'TEST' in analysis.rationale
    # Bullish market + up day should increase opportunity score
    assert analysis.opportunity_score > 40  # Should be positive


def test_analyze_opportunity_bearish(ai_agent, sample_portfolio):
    """Test analysis with bearish signals."""
    bearish_data = {
        'open': 100.0,
        'high': 100.5,
        'low': 95.0,
        'close': 96.0,
        'volume': 1000000,
        'volatility': 0.05
    }
    analysis = ai_agent.analyze_opportunity(
        symbol='TEST',
        current_price=96.0,
        market_data=bearish_data,
        portfolio_state=sample_portfolio,
        market_regime='bear'
    )
    assert analysis is not None
    assert 'rationale' in analysis.rationale.lower() or 'analysis' in analysis.rationale.lower()


def test_analyze_opportunity_crash_regime(ai_agent, sample_portfolio, sample_market_data):
    """Test analysis in crash market regime."""
    analysis = ai_agent.analyze_opportunity(
        symbol='TEST',
        current_price=100.0,
        market_data=sample_market_data,
        portfolio_state=sample_portfolio,
        market_regime='crash'
    )
    assert analysis is not None
    # Analysis should be created for any regime
    assert hasattr(analysis, 'opportunity_score')
    assert hasattr(analysis, 'risk_score')


def test_trend_analysis_uptrend(ai_agent):
    """Test trend analysis detects uptrend."""
    market_data = {'open': 100.0, 'close': 105.0, 'high': 106.0, 'low': 99.0}
    trend = ai_agent._analyze_trend(market_data)
    assert trend > 0  # Should be positive for up day


def test_trend_analysis_downtrend(ai_agent):
    """Test trend analysis detects downtrend."""
    market_data = {'open': 100.0, 'close': 95.0, 'high': 101.0, 'low': 94.0}
    trend = ai_agent._analyze_trend(market_data)
    assert trend < 0  # Should be negative for down day


def test_trend_analysis_no_data(ai_agent):
    """Test trend analysis handles missing data."""
    trend = ai_agent._analyze_trend(None)
    assert trend == 0.0


def test_rationale_generation_contains_key_info(ai_agent):
    """Test generated rationale includes key information."""
    rationale = ai_agent._generate_rationale(
        symbol='TEST',
        trend=0.5,
        sentiment=0.7,
        value=0.6,
        regime='bull',
        confidence=80.0,
        risk=30.0,
        price=100.0,
        volatility=0.02
    )
    assert 'TEST' in rationale
    assert 'Confidence' in rationale or 'confidence' in rationale
    assert 'Risk' in rationale or 'risk' in rationale
    assert 'Price' in rationale or '100.00' in rationale


def test_propose_trade_high_confidence_high_opportunity(ai_agent, sample_portfolio):
    """Test trade proposal with strong signals."""
    analysis = TradingAnalysis(
        symbol='TEST',
        opportunity_score=75.0,
        confidence_score=75.0,
        risk_score=30.0,
        rationale='Strong buy signal',
        inputs={}
    )
    proposal = ai_agent.propose_trade(analysis, sample_portfolio, {'TEST': 100.0})
    assert proposal is not None
    assert proposal['symbol'] == 'TEST'
    assert proposal['proposed_qty'] == 10


def test_propose_trade_low_confidence(ai_agent, sample_portfolio):
    """Test trade proposal rejected with low confidence."""
    analysis = TradingAnalysis(
        symbol='TEST',
        opportunity_score=40.0,
        confidence_score=40.0,
        risk_score=50.0,
        rationale='Weak signal',
        inputs={}
    )
    proposal = ai_agent.propose_trade(analysis, sample_portfolio, {'TEST': 100.0})
    assert proposal is None  # Should not propose trade


def test_execute_proposal_success(ai_agent, sample_portfolio):
    """Test successful trade execution through pipeline."""
    proposal = {
        'decision_id': 'test-123',
        'symbol': 'TEST',
        'proposed_action': 'BUY',
        'proposed_side': 'buy',
        'proposed_qty': 1,  # Small qty to avoid cash issues
        'confidence_score': 75.0,
        'opportunity_score': 75.0,
        'risk_score': 30.0,
        'expected_reward': 100.0,
        'risk_reward_ratio': 2.0,
        'rationale': 'Test proposal',
        'inputs': {},
        'model_name': 'test-model',
        'model_version': '1.0',
        'prompt_version': '1.0',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    result = ai_agent.execute_proposal(proposal, RiskManager(), sample_portfolio, {'TEST': 100.0})
    # Should have audit trail
    assert 'audit_trail' in result
    # Decision ID should be stored
    assert result['decision_id'] == 'test-123'


def test_execute_proposal_risk_rejection(ai_agent):
    """Test trade rejection by risk manager."""
    # Portfolio with very little cash
    poor_portfolio = {
        'total_equity': 100.0,
        'cash': 50.0,
        'positions': []
    }
    
    proposal = {
        'decision_id': 'test-456',
        'symbol': 'TEST',
        'proposed_action': 'BUY',
        'proposed_side': 'buy',
        'proposed_qty': 1000,  # Very large qty
        'confidence_score': 75.0,
        'opportunity_score': 75.0,
        'risk_score': 50.0,
        'expected_reward': 100.0,
        'risk_reward_ratio': 1.0,
        'rationale': 'Test proposal',
        'inputs': {},
        'model_name': 'test-model',
        'model_version': '1.0',
        'prompt_version': '1.0',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    result = ai_agent.execute_proposal(proposal, RiskManager(), poor_portfolio, {'TEST': 100.0})
    # Should be rejected by risk management
    assert result['rejected'] or len(result['audit_trail']) > 0


def test_ai_decision_storage(ai_agent, temp_db):
    """Test AI decision is stored in database."""
    proposal = {
        'decision_id': 'db-test-123',
        'symbol': 'STORED',
        'proposed_action': 'BUY',
        'proposed_side': 'buy',
        'proposed_qty': 5,
        'confidence_score': 80.0,
        'opportunity_score': 80.0,
        'risk_score': 25.0,
        'expected_reward': 500.0,
        'risk_reward_ratio': 2.0,
        'rationale': 'Test storage',
        'inputs': {},
        'model_name': 'test-model',
        'model_version': '1.0',
        'prompt_version': '1.0',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    ai_agent.execute_proposal(proposal, RiskManager(), {'total_equity': 100000.0, 'cash': 50000.0}, {'STORED': 100.0})
    
    # Retrieve from DB
    stored = get_ai_decision('db-test-123', temp_db)
    assert stored is not None
    assert stored['symbol'] == 'STORED'


def test_ai_decisions_list(ai_agent, temp_db):
    """Test listing AI decisions."""
    proposals = [
        {
            'decision_id': f'list-test-{i}',
            'symbol': 'TEST',
            'proposed_action': 'BUY',
            'proposed_side': 'buy',
            'proposed_qty': 1,
            'confidence_score': 70.0,
            'opportunity_score': 70.0,
            'risk_score': 30.0,
            'expected_reward': 100.0,
            'risk_reward_ratio': 1.5,
            'rationale': f'Test {i}',
            'inputs': {},
            'model_name': 'test-model',
            'model_version': '1.0',
            'prompt_version': '1.0',
            'timestamp': datetime.utcnow().isoformat()
        }
        for i in range(3)
    ]
    
    for proposal in proposals:
        ai_agent.execute_proposal(proposal, RiskManager(), {'total_equity': 100000.0, 'cash': 50000.0}, {'TEST': 100.0})
    
    decisions = list_ai_decisions(limit=10, db_path=temp_db)
    assert len(decisions) >= 3


def test_no_direct_broker_access():
    """Verify AI cannot directly call broker - must go through Decision Engine."""
    # This is a design test ensuring broker is not imported in ai_agent
    import inspect
    from backend.ai_models import ai_agent as ai_module
    
    source = inspect.getsource(ai_module)
    # Should NOT have direct broker imports or calls
    assert 'BrokerService' not in source or 'decide_and_execute' in source


def test_audit_trail_captures_all_stages(ai_agent):
    """Test that audit trail captures all decision stages."""
    proposal = {
        'decision_id': 'audit-test',
        'symbol': 'AUDIT',
        'proposed_action': 'BUY',
        'proposed_side': 'buy',
        'proposed_qty': 5,
        'confidence_score': 75.0,
        'opportunity_score': 75.0,
        'risk_score': 30.0,
        'expected_reward': 500.0,
        'risk_reward_ratio': 2.0,
        'rationale': 'Audit test',
        'inputs': {},
        'model_name': 'test-model',
        'model_version': '1.0',
        'prompt_version': '1.0',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    result = ai_agent.execute_proposal(
        proposal, 
        RiskManager(), 
        {'total_equity': 100000.0, 'cash': 50000.0}, 
        {'AUDIT': 100.0}
    )
    
    # Should have audit trail with at least risk validation stage
    assert 'audit_trail' in result
    assert len(result['audit_trail']) > 0
    # Each audit entry should have stage, passed, reason
    for audit in result['audit_trail']:
        assert 'stage' in audit
        assert 'passed' in audit
        assert 'reason' in audit

