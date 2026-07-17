from typing import Dict, Optional
from backend.paper_trading.paper_engine import PaperTradingEngine
from backend.paper_trading.paper_db import get_paper_portfolio

# The decision engine has one paper-only execution path.  It deliberately does
# not import the IBKR or legacy broker services.
_default_paper_engine = PaperTradingEngine()


def decide_and_execute(signal: Dict, db_path: Optional[str] = None) -> Dict:
    """Submit a previously approved signal to the guarded paper engine."""
    engine = _default_paper_engine if db_path is None else PaperTradingEngine(db_path=db_path)
    symbol = signal.get('symbol')
    qty = float(signal.get('qty', 0))
    side = signal.get('side')
    price = float(signal.get('price') or signal.get('current_price') or 100.0)
    portfolio = get_paper_portfolio(db_path=engine.db_path) or {}
    return engine.execute_trade(
        symbol=symbol,
        qty=qty,
        side=side,
        market_data={'close': price},
        portfolio_state={'total_equity': portfolio.get('total_equity', 0.0)},
        market_regime=signal.get('market_regime', 'neutral'),
    )
