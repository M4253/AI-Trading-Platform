from backend.db.db import get_portfolio


def get_portfolio_view(db_path=None):
    return get_portfolio(db_path)
