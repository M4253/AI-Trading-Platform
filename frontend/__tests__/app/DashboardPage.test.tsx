import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { renderToString } from 'react-dom/server'
import DashboardPage from '@/app/dashboard/page'
import API from '@/lib/api'

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}))

jest.mock('@/components/Layout', () => {
  return ({ user, children }: { user?: string | null; children: React.ReactNode }) => (
    <div>
      <span data-testid="dashboard-user">{user || ''}</span>
      {children}
    </div>
  )
})

jest.mock('@/components/PortfolioCard', () => () => null)
jest.mock('@/components/EquityCurve', () => () => null)
jest.mock('@/components/DrawdownChart', () => () => null)
jest.mock('@/components/PositionsTable', () => () => null)
jest.mock('@/components/OrdersTable', () => () => null)
jest.mock('@/components/RiskDashboard', () => () => null)
jest.mock('@/components/AIDecisionsTable', () => () => null)
jest.mock('@/components/AIExecutionSettings', () => () => null)
jest.mock('@/components/MarketIntelligencePanel', () => () => null)
jest.mock('@/components/TradingControls', () => () => null)

jest.mock('@/lib/api', () => {
  const actual = jest.requireActual('@/lib/api')
  return {
    __esModule: true,
    ...actual,
    default: {
      get: jest.fn(),
      post: jest.fn(),
    },
  }
})

const mockedApi = API as jest.Mocked<typeof API>

describe('DashboardPage storage safety', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    sessionStorage.clear()
    localStorage.clear()
  })

  it('server-renders without a browser window or storage access', () => {
    const windowDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'window')
    Object.defineProperty(globalThis, 'window', { configurable: true, value: undefined })

    try {
      expect(() => renderToString(<DashboardPage />)).not.toThrow()
      expect(mockedApi.get).not.toHaveBeenCalled()
    } finally {
      if (windowDescriptor) Object.defineProperty(globalThis, 'window', windowDescriptor)
    }
  })

  it('hydrates the logged-in user from browser session storage', async () => {
    sessionStorage.setItem('token', 'opaque-session-token')
    sessionStorage.setItem('user', 'demo@example.com')
    mockedApi.get.mockImplementation(async (path: string) => {
      if (path === '/portfolio') return { data: { trading_status: 'stopped' } }
      if (path === '/paper/positions') return { data: { positions: [] } }
      if (path === '/paper/orders') return { data: { orders: [] } }
      return { data: { decisions: [] } }
    })

    render(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-user')).toHaveTextContent('demo@example.com')
    })
    expect(mockedApi.get).toHaveBeenCalledWith('/portfolio')
  })
})
