# AI Trading Platform - Frontend

Next.js web dashboard for the AI Trading Platform paper trading engine.

## Features

- 🔐 Secure login page
- 📊 Portfolio dashboard with equity, cash, and P&L
- 📈 Equity curve and drawdown charts
- 💼 Open positions display
- 📋 Orders and trades history
- 🤖 Auditable AI decisions that analyze supplied charts, indicators, news, market data, and paper portfolio state
- 🧠 AI reasoning, confidence, execution outcome, and manual paper-approval controls in the dashboard
- 🧪 Selectable local AI model policy with manual approval by default and automatic paper execution as the only automatic option
- ⚠️ Risk monitoring dashboard with guardrail status
- 🎮 Trading controls (start, pause, stop all trading)
- ⚙️ Broker settings: add, edit, remove, and locally save disconnected IBKR configurations
- 🧪 Deterministic mock-only broker configuration tests (no network connection)
- 🛑 Always-visible STOP ALL TRADING control
- 📱 Responsive design for desktop, tablet, and mobile

## Setup

```bash
# Install dependencies
npm install

# Create environment file
cp .env.example .env.local

# Start development server
npm run dev
```

## Environment Variables

- `NEXT_PUBLIC_BACKEND_URL`: Backend API URL (default: http://localhost:8000)

## Pages

- `/` - Redirects to login
- `/login` - Secure login page
- `/dashboard` - Main portfolio dashboard
- `/dashboard/broker-settings` - Broker settings and local mock validation

## Components

- `Layout` - Main layout with navigation and footer
- `PortfolioCard` - Display portfolio metrics
- `EquityCurve` - Equity curve chart
- `DrawdownChart` - Drawdown history chart
- `PositionsTable` - Open positions table
- `OrdersTable` - Orders history table
- `AIDecisionsTable` - AI decisions with reasoning, scores, outcomes, and paper approval controls
- `AIExecutionSettings` - Paper-only AI model and execution-policy settings
- `RiskDashboard` - Risk guardrails monitoring
- `TradingControls` - Start/pause/stop trading buttons

## Testing

```bash
npm run test        # Run tests in watch mode
npm run test:ci    # Run tests in CI mode
```

## Backend Integration

The frontend connects to the backend API:

- `GET /portfolio` - Portfolio summary
- `GET /paper/positions` - Current positions
- `GET /paper/orders` - Orders history
- `GET /ai/decisions` - AI trading decisions
- `POST /ai/decisions` - Analyze and persist a decision under the saved paper-only policy
- `POST /ai/decisions/{id}/approve` - Manually approve one decision for guarded paper execution
- `POST /ai/decisions/{id}/reject` - Record a manual rejection without execution
- `GET/PATCH /ai/settings` - Read or update manual/automatic-paper AI settings
- `POST /paper/start` - Start paper trading
- `POST /paper/pause` - Pause paper trading
- `POST /paper/stop-all` - Stop all trading (emergency)

## Security Notes

- No real IBKR credentials are requested, stored, or displayed
- Broker metadata is stored locally with restricted file permissions where supported
- Live trading remains disabled in the frontend and backend
- AI settings only allow manual approval or automatic **paper** execution; they never connect to a real broker
- AI context and outcomes are stored locally for auditability; no real API keys or broker credentials are requested
- Broker settings display Disconnected, Paper Ready, and Live Locked states
- All sensitive operations require user confirmation
- Demo login is for testing only

## Build for Production

```bash
npm run build
npm start
```

The application will be available at `http://localhost:3000`.
