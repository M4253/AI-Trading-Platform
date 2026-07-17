from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from backend.backtesting.backtester import Backtester, BacktestConfig
from backend.backtesting.data_provider import CSVDataProvider
from backend.db.db import get_conn
from backend.security.audit import record_audit_event

router = APIRouter(prefix='/backtest', tags=['backtest'])


class BacktestRequest(BaseModel):
    strategy_name: str
    strategy_version: str
    symbols: List[str]
    start_date: str
    end_date: str
    initial_cash: float = 100000.0
    commission_rate: float = 0.001
    slippage_pct: float = 0.01
    in_sample_ratio: float = 0.7
    seed: int = 42


@router.post('/start')
def start_backtest(req: BacktestRequest, request: Request):
    """Start a new backtest run."""
    try:
        data_provider = CSVDataProvider()
        config = BacktestConfig(
            strategy_name=req.strategy_name,
            strategy_version=req.strategy_version,
            data_provider=data_provider,
            start_date=datetime.fromisoformat(req.start_date),
            end_date=datetime.fromisoformat(req.end_date),
            in_sample_ratio=req.in_sample_ratio,
            initial_cash=req.initial_cash,
            commission_rate=req.commission_rate,
            slippage_pct=req.slippage_pct,
            seed=req.seed,
            symbols=req.symbols
        )
        backtester = Backtester(config)
        # Dummy strategy: buy on dip, sell on rise
        def dummy_strategy(current_bars, portfolio):
            signals = []
            for symbol, bar in current_bars.items():
                if bar.close < bar.open * 0.98 and symbol not in portfolio.positions:
                    signals.append({'symbol': symbol, 'qty': 10, 'side': 'buy'})
            return signals
        
        results = backtester.run(dummy_strategy)
        record_audit_event('backtest', 'backtest_completed', 'backtest', backtester.backtest_id, request=request)
        return {'backtest_id': backtester.backtest_id, 'results': results}
    except Exception as e:
        raise HTTPException(status_code=400, detail='Backtest could not be completed') from e


@router.get('/results/{backtest_id}')
def get_results(backtest_id: str):
    """Fetch backtest results from DB."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM backtest_results WHERE backtest_id = ?', (backtest_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='Backtest not found')
    return dict(row)


@router.get('/runs')
def list_backtests():
    """List all backtest runs."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, strategy_name, strategy_version, start_date, end_date, status FROM backtest_runs ORDER BY created_at DESC LIMIT 50')
    rows = cur.fetchall()
    return [dict(r) for r in rows]
