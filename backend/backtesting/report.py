from typing import Dict, List, Any
from datetime import datetime
import json


class BacktestReport:
    def __init__(self, results: Dict[str, Any]):
        self.results = results

    def generate_text_report(self) -> str:
        """Generate human-readable text report."""
        r = self.results
        report_lines = [
            "=" * 80,
            "BACKTESTING REPORT",
            "=" * 80,
            f"Backtest ID: {r.get('backtest_id', 'N/A')}",
            f"Report Generated: {datetime.utcnow().isoformat()}",
            "",
            "PERFORMANCE METRICS",
            "-" * 80,
            f"Total Return:              {r.get('total_return', 0):.2%}",
            f"Annualized Return:         {r.get('annualized_return', 0):.2%}",
            f"Final Equity:              ${r.get('final_equity', 0):,.2f}",
            f"Realized P&L:              ${r.get('realized_pnl', 0):,.2f}",
            "",
            "RISK METRICS",
            "-" * 80,
            f"Max Drawdown:              {r.get('max_drawdown', 0):.2%}",
            f"Volatility (Annualized):   {r.get('volatility', 0):.2%}",
            f"Sharpe Ratio:              {r.get('sharpe_ratio', 0):.4f}",
            f"Adjusted Sharpe Ratio:     {r.get('adjusted_sharpe', 0):.4f}",
            f"Sortino Ratio:             {r.get('sortino_ratio', 0):.4f}",
            "",
            "TRADE STATISTICS",
            "-" * 80,
            f"Number of Trades:          {r.get('num_trades', 0)}",
            f"Win Rate:                  {r.get('win_rate', 0):.2%}",
            f"Profit Factor:             {r.get('profit_factor', 0):.2f}",
            f"Average Win:               ${r.get('avg_win', 0):,.2f}",
            f"Average Loss:              ${r.get('avg_loss', 0):,.2f}",
            "",
            "TRANSACTION COSTS",
            "-" * 80,
            f"Commission Costs:          ${r.get('commission_costs', 0):,.2f}",
            f"Spread Costs:              ${r.get('spread_costs', 0):,.2f}",
            f"Slippage Costs:            ${r.get('slippage_costs', 0):,.2f}",
            f"Total Costs:               ${r.get('commission_costs', 0) + r.get('spread_costs', 0) + r.get('slippage_costs', 0):,.2f}",
            "",
            "PORTFOLIO METRICS",
            "-" * 80,
            f"Exposure Time:             {r.get('exposure_time', 0):.2%}",
            f"Turnover:                  {r.get('turnover', 0):.2f}",
            "",
        ]

        # Regime breakdown
        if r.get('regime_breakdown'):
            report_lines.extend(["", "RESULTS BY MARKET REGIME", "-" * 80])
            for regime, metrics in r['regime_breakdown'].items():
                report_lines.append(f"{regime.upper()}")
                report_lines.append(f"  Trades: {metrics.get('trades', 0)}, "
                                    f"Wins: {metrics.get('wins', 0)}, "
                                    f"Total P&L: ${metrics.get('total_pnl', 0):,.2f}")

        report_lines.extend(["", "=" * 80])
        return "\n".join(report_lines)

    def to_json(self) -> str:
        """Export results as JSON."""
        return json.dumps(self.results, indent=2, default=str)

    def to_dict(self) -> Dict:
        """Return results dict."""
        return self.results

