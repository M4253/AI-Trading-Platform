# AI Trading Platform

AI Trading Platform is a local, paper-only research and simulation application. It combines backtesting, public/no-key market intelligence, an auditable AI decision engine, risk checks, and a simulated paper broker.

> **Safety status:** this repository is not approved for real-money trading. Live execution is technically locked, Interactive Brokers remains disconnected, and the only execution path is the local `PaperTradingEngine`.

## What is included

- Backtesting with deterministic controls.
- Paper portfolio, order, position, risk, and emergency-stop controls.
- AI trade proposals using chart, indicator, news, market, economic, and paper-portfolio context.
- Manual approval or automatic **paper** execution only.
- Modular public market data, financial-news sentiment, economic calendar, watchlists, and scanner.
- Credential-free, mock-only Interactive Brokers configuration metadata.
- Structured logs, redacted audit events, health/readiness/dependency endpoints, CORS/security headers, rate limits, and a fail-closed production authentication boundary.

## Installation

Requirements:

- Python 3.11 or later
- Node.js 20 or later
- pnpm 9 or later

Create an isolated Python environment and install the backend dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Install the dashboard dependencies:

```bash
cd frontend
pnpm install --frozen-lockfile
cd ..
```

Copy the safe development template if local configuration is needed. Do not put any broker credential in an environment file.

```bash
cp .env.example .env
```

`.env` and all production environment files are excluded from Git; `.env.example` contains no secret.

## Run the local paper application

Start the backend from the repository root:

```bash
APP_ENV=development AUTH_REQUIRED=false uvicorn backend.main:app --reload
```

Start the dashboard in a second terminal:

```bash
cd frontend
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 pnpm dev
```

Open `http://localhost:3000`. The local development demo is `demo@example.com` / `demo`; it is handled by the backend, which issues an opaque session token stored only for the browser session. This demo endpoint is disabled when `APP_ENV=production`.

Useful operational endpoints:

- `GET /health` — process health and paper-only status.
- `GET /ready` — database/startup readiness.
- `GET /dependencies` — database, AI, provider-fallback, and broker-lock status.
- `GET /audit-events` — local redacted operational audit trail (protect this endpoint in production).

## Paper-trading operation

1. Start paper trading from the dashboard or `POST /paper/start`.
2. Load market context, create an AI decision, and leave the default **Manual approval** setting in place unless testing automatic paper execution.
3. Approve only a saved decision. The decision engine sends it through the risk engine and then the simulated paper broker.
4. Review paper orders, portfolio, AI reasoning, confidence, and audit history.

The Broker Settings page can save non-secret Interactive Brokers metadata and run only deterministic mock tests. A `Paper Ready` status means the local metadata passed a mock check; it does **not** mean that IBKR was contacted, authenticated, or verified.

### Emergency stop

Use **STOP ALL TRADING** on the dashboard or `POST /paper/stop-all`. It records an audit/risk event, persists `trading_halted=true`, and blocks every subsequent new paper order, including a pending AI approval. It does not liquidate existing paper positions. Restarting the process does not clear the halt; intentionally starting paper trading again is required.

## Tests and checks

From the repository root:

```bash
python3 -m pytest -q
python3 scripts/security_check.py
python3 -m pip check
cd frontend && pnpm test:ci
cd frontend && pnpm exec tsc --noEmit
cd frontend && pnpm build
```

`pnpm lint` is retained for compatibility with the original dashboard, but recent Next.js releases no longer provide `next lint`; use the TypeScript check above until the project migrates to an explicit ESLint flat configuration.

## Database backup and recovery

The local SQLite database is `backend/data/trading.db` and is deliberately ignored by Git. Stop the backend before copying it. See [Database Backup and Recovery](docs/DATABASE_BACKUP_RECOVERY.md) for backup, restore, permissions, and recovery validation steps.

## Production and security documentation

- [Production deployment guide](docs/PRODUCTION_DEPLOYMENT.md)
- [Security checklist](docs/SECURITY_CHECKLIST.md)
- [Paper-trading validation checklist](docs/PAPER_TRADING_VALIDATION.md)
- [Go-live checklist](docs/GO_LIVE_CHECKLIST.md)
- [Phase 11 readiness report](docs/READINESS_REPORT.md)

## Limitations and future IBKR work

This build deliberately has no live-broker path. It does not collect broker credentials, does not connect to IBKR, does not submit real orders, and has no real-money approval. Before any separate live-trading project could be considered, the owner would need to approve it after independent security review, a secret manager and production identity provider are integrated, real IBKR paper/live verification is completed under controlled conditions, and an extended forward paper-trading record is reviewed. Those steps are intentionally outside this repository's current execution capability.
