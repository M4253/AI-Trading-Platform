import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import MarketIntelligencePanel from '@/components/MarketIntelligencePanel'
import API from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}))

const mockedApi = API as jest.Mocked<typeof API>

const context = {
  symbol: 'AAPL',
  quote: { price: 200, change_pct: 1.5 },
  indicators: { trend_score: 0.42, rsi: 61 },
  news_sentiment: { label: 'positive', score: 0.5 },
  economic_calendar: { events: [{ event: 'Central bank decision' }] },
  market_health: { market_data_provider: 'fixture_market', is_fallback: false },
}

describe('MarketIntelligencePanel', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockedApi.get.mockImplementation(async (path: string) => {
      if (path === '/market/health') {
        return { data: { status: 'healthy', providers: [{ name: 'fixture_market', category: 'market_data', is_free: true, status: 'available' }] } }
      }
      if (path === '/market/watchlists') {
        return { data: { watchlists: [{ id: 'default', name: 'Default Watchlist', symbols: ['AAPL'] }] } }
      }
      return { data: context }
    })
    mockedApi.post.mockImplementation(async (path: string) => {
      if (path === '/market/scanner') {
        return { data: { count: 1, results: [{ symbol: 'AAPL', price: 200, trend_score: 0.42, news_sentiment: 0.5, scanner_score: 76 }] } }
      }
      return { data: { decision: { proposed_action: 'BUY' } } }
    })
  })

  it('shows provider health, market context, scanner results, and a paper-only AI action', async () => {
    const onDecisionCreated = jest.fn()
    render(<MarketIntelligencePanel onDecisionCreated={onDecisionCreated} />)

    expect(await screen.findByText('Market Health: healthy')).toBeInTheDocument()
    expect(screen.getByText('fixture_market')).toBeInTheDocument()
    expect(screen.getByText(/no paid api, api key, broker account/i)).toBeInTheDocument()
    expect(await screen.findByText('AAPL')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'AAPL' }))
    expect(await screen.findByText(/AAPL market context loaded/i)).toBeInTheDocument()
    expect(screen.getByText(/Trend 0.42/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Run Market Scanner' }))
    expect(await screen.findByText('Scanner Results')).toBeInTheDocument()
    expect(screen.getByText('76')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Create AI Paper Decision' }))
    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/market/ai-decisions/AAPL'))
    expect(await screen.findByText(/AI decision recorded for AAPL: BUY/i)).toBeInTheDocument()
    expect(onDecisionCreated).toHaveBeenCalled()
  })
})
