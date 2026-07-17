# AI Trading Platform - Frontend

Next.js web dashboard for the AI Trading Platform paper trading engine.

## Features

- 🔐 Secure login page
- 📊 Portfolio dashboard with equity, cash, and P&L
- 📈 Equity curve and drawdown charts
- 💼 Open positions display
- 📋 Orders and trades history
- 🤖 AI trading decisions with confidence, opportunity, and risk scores
- ⚠️ Risk monitoring dashboard with guardrail status
- 🎮 Trading controls (start, pause, stop all trading)
- ⚙️ Broker settings page (disconnected, no real credentials)
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
- `/dashboard/broker-settings` - Broker settings (disconnected)

## Components

- `Layout` - Main layout with navigation and footer
- `PortfolioCard` - Display portfolio metrics
- `EquityCurve` - Equity curve chart
- `DrawdownChart` - Drawdown history chart
- `PositionsTable` - Open positions table
- `OrdersTable` - Orders history table
- `AIDecisionsTable` - AI decisions with scores
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
- `POST /paper/start` - Start paper trading
- `POST /paper/pause` - Pause paper trading
- `POST /paper/stop-all` - Stop all trading (emergency)

## Security Notes

- No real IBKR credentials are stored or displayed
- Live trading remains disabled at the frontend level
- Broker settings UI shows connection status as "Not Connected"
- All sensitive operations require user confirmation
- Demo login is for testing only

## Build for Production

```bash
npm run build
npm start
```

The application will be available at `http://localhost:3000`.
