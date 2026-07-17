"""REST endpoints for AI Trading Agent."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from backend.ai_models.ai_agent import AIAgent
from backend.db.ai_db import get_ai_decision, list_ai_decisions
from backend.db.db import get_portfolio
from backend.risk_engine.risk_manager import RiskManager

router = APIRouter(prefix='/ai', tags=['ai'])

# Global agent instance
_agent = AIAgent(model_name='claude-haiku', model_version='1.0', prompt_version='1.0')
_risk_manager = RiskManager()


class AIAnalysisRequest(BaseModel):
    symbol: str
    current_price: float
    market_data: Optional[Dict] = None
    market_regime: str = 'neutral'
    fundamentals: Optional[Dict] = None
    sentiment: Optional[Dict] = None
    macro_data: Optional[Dict] = None


class AITradeProposalRequest(BaseModel):
    symbol: str
    current_price: float
    market_data: Optional[Dict] = None
    market_regime: str = 'neutral'
    fundamentals: Optional[Dict] = None
    sentiment: Optional[Dict] = None
    macro_data: Optional[Dict] = None
    auto_execute: bool = False


@router.post('/analyze')
def analyze_opportunity(req: AIAnalysisRequest):
    """Get AI analysis for a symbol without proposing trade."""
    try:
        portfolio = get_portfolio()
        analysis = _agent.analyze_opportunity(
            symbol=req.symbol,
            current_price=req.current_price,
            market_data=req.market_data or {},
            portfolio_state=portfolio,
            market_regime=req.market_regime,
            fundamentals=req.fundamentals,
            sentiment=req.sentiment,
            macro_data=req.macro_data
        )
        return {
            'symbol': analysis.symbol,
            'opportunity_score': analysis.opportunity_score,
            'confidence_score': analysis.confidence_score,
            'risk_score': analysis.risk_score,
            'rationale': analysis.rationale
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/propose-trade')
def propose_trade(req: AITradeProposalRequest):
    """Get AI trade proposal (does not execute)."""
    try:
        portfolio = get_portfolio()
        current_prices = {req.symbol: req.current_price}
        
        analysis = _agent.analyze_opportunity(
            symbol=req.symbol,
            current_price=req.current_price,
            market_data=req.market_data or {},
            portfolio_state=portfolio,
            market_regime=req.market_regime,
            fundamentals=req.fundamentals,
            sentiment=req.sentiment,
            macro_data=req.macro_data
        )
        
        proposal = _agent.propose_trade(analysis, portfolio, current_prices)
        if not proposal:
            return {'proposal': None, 'reason': 'Thresholds not met'}
        
        if req.auto_execute:
            result = _agent.execute_proposal(proposal, _risk_manager, portfolio, current_prices)
            return result
        else:
            return {'proposal': proposal, 'awaiting_approval': True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/execute-proposal')
def execute_proposal(proposal_dict: Dict):
    """Execute an AI trade proposal through full pipeline."""
    try:
        portfolio = get_portfolio()
        current_prices = {proposal_dict['symbol']: proposal_dict.get('price', 100.0)}
        
        result = _agent.execute_proposal(proposal_dict, _risk_manager, portfolio, current_prices)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/decisions')
def list_decisions(limit: int = 50):
    """List all AI decisions."""
    try:
        decisions = list_ai_decisions(limit=limit)
        return {'decisions': decisions, 'count': len(decisions)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/decisions/{decision_id}')
def get_decision(decision_id: str):
    """Get detailed view of single AI decision."""
    try:
        decision = get_ai_decision(decision_id)
        if not decision:
            raise HTTPException(status_code=404, detail='Decision not found')
        return decision
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

