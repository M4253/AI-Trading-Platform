from backend.paper_trading.paper_db import (
    get_paper_portfolio, get_paper_positions, get_paper_trading_state,
)


def get_portfolio_view(db_path=None):
    """Return the active paper account with Phase 3-compatible keys."""
    portfolio = get_paper_portfolio(db_path) or {}
    return {
        **portfolio,
        'cash': portfolio.get('current_cash', 0.0),
        'positions': get_paper_positions(db_path),
        'unrealized_pnl': portfolio.get('total_unrealised_pnl', 0.0),
        'trading_status': get_paper_trading_state('status', db_path) or 'stopped',
        'paper_trading': True,
    }
