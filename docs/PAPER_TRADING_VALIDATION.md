# Paper-Trading Validation Checklist

- [ ] `GET /health`, `GET /ready`, and `GET /dependencies` report expected paper-only status.
- [ ] Broker Settings shows **Disconnected** by default and any test response says `mock`.
- [ ] No account number, password, API key, or broker token is requested by the UI.
- [ ] A market context displays data source/fallback state, news sentiment, economic events, and AI-ready context.
- [ ] A new AI decision stores reasoning, confidence, inputs, and a database audit trail.
- [ ] Manual approval creates only a paper order after Decision Engine and Risk Engine checks pass.
- [ ] Automatic mode, if tested, is set only to `automatic_paper` and never exposes a live option.
- [ ] A rejected decision produces no paper order.
- [ ] STOP ALL TRADING blocks a direct paper request and a pending AI approval.
- [ ] Restart the backend and confirm paper portfolio state and the stop state persist.
- [ ] Backtesting produces a result without affecting the paper portfolio.
- [ ] Audit records exist for settings changes, approvals/rejections, emergency stops, and trade rejections.
