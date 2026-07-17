'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'
import PortfolioCard from '@/components/PortfolioCard'
import EquityCurve from '@/components/EquityCurve'
import DrawdownChart from '@/components/DrawdownChart'
import PositionsTable from '@/components/PositionsTable'
import OrdersTable from '@/components/OrdersTable'
import RiskDashboard from '@/components/RiskDashboard'
import AIDecisionsTable from '@/components/AIDecisionsTable'
import AIExecutionSettings from '@/components/AIExecutionSettings'
import MarketIntelligencePanel from '@/components/MarketIntelligencePanel'
import TradingControls from '@/components/TradingControls'
import API, { getSessionValue } from '@/lib/api'

export default function DashboardPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [portfolio, setPortfolio] = useState<any>(null)
  const [positions, setPositions] = useState<any[]>([])
  const [orders, setOrders] = useState<any[]>([])
  const [aiDecisions, setAiDecisions] = useState<any[]>([])
  const [error, setError] = useState('')
  const [tradingStatus, setTradingStatus] = useState('stopped')
  const [user, setUser] = useState<string | null>(null)
  const [updatingDecisionId, setUpdatingDecisionId] = useState<string | null>(null)

  useEffect(() => {
    const token = getSessionValue('token')
    if (!token) {
      router.push('/login')
      return
    }
    setUser(getSessionValue('user'))
    loadData()
  }, [router])

  const loadData = async () => {
    try {
      setLoading(true)
      const [portfolioRes, positionsRes, ordersRes, aiRes] = await Promise.all([
        API.get('/portfolio'),
        API.get('/paper/positions'),
        API.get('/paper/orders'),
        API.get('/ai/decisions?limit=10'),
      ])

      setPortfolio(portfolioRes.data)
      setPositions(positionsRes.data.positions || [])
      setOrders(ordersRes.data.orders || [])
      setAiDecisions(aiRes.data.decisions || [])
      setTradingStatus(portfolioRes.data.trading_status || 'stopped')
      setError('')
    } catch (err: any) {
      console.error('Error loading data:', err)
      setError(err.response?.data?.detail || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = () => {
    loadData()
  }

  const handleStartTrading = async () => {
    try {
      await API.post('/paper/start')
      setTradingStatus('running')
      handleRefresh()
    } catch (err) {
      setError('Failed to start trading')
    }
  }

  const handlePauseTrading = async () => {
    try {
      await API.post('/paper/pause')
      setTradingStatus('paused')
      handleRefresh()
    } catch (err) {
      setError('Failed to pause trading')
    }
  }

  const handleStopAllTrading = async () => {
    const confirmed = window.confirm(
      'STOP ALL TRADING? This will immediately block new orders. Confirm?'
    )
    if (confirmed) {
      try {
        await API.post('/paper/stop-all')
        setTradingStatus('stopped')
        handleRefresh()
      } catch (err) {
        setError('Failed to stop trading')
      }
    }
  }

  const handleApproveDecision = async (decisionId: string) => {
    try {
      setUpdatingDecisionId(decisionId)
      setError('')
      await API.post(`/ai/decisions/${decisionId}/approve`)
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to approve the paper decision')
    } finally {
      setUpdatingDecisionId(null)
    }
  }

  const handleRejectDecision = async (decisionId: string) => {
    if (!window.confirm('Reject this AI decision without placing a paper order?')) return
    try {
      setUpdatingDecisionId(decisionId)
      setError('')
      await API.post(`/ai/decisions/${decisionId}/reject`, { reason: 'Rejected from dashboard' })
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to reject the AI decision')
    } finally {
      setUpdatingDecisionId(null)
    }
  }

  return (
    <Layout user={user} onRefresh={handleRefresh}>
      <div className="space-y-6">
        {/* Trading Controls */}
        <TradingControls
          status={tradingStatus}
          onStart={handleStartTrading}
          onPause={handlePauseTrading}
          onStop={handleStopAllTrading}
        />

        <AIExecutionSettings onChanged={handleRefresh} />

        <MarketIntelligencePanel onDecisionCreated={handleRefresh} />

        {/* Error Alert */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>
            {/* Portfolio Overview */}
            {portfolio && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <PortfolioCard
                  title="Account Equity"
                  value={`$${portfolio.total_equity?.toFixed(2) || '0.00'}`}
                  change={portfolio.total_unrealised_pnl}
                  icon="💰"
                />
                <PortfolioCard
                  title="Cash"
                  value={`$${portfolio.current_cash?.toFixed(2) || '0.00'}`}
                  icon="💵"
                />
                <PortfolioCard
                  title="Realised P&L"
                  value={`$${portfolio.total_realised_pnl?.toFixed(2) || '0.00'}`}
                  change={portfolio.total_realised_pnl}
                  icon="📈"
                />
                <PortfolioCard
                  title="Unrealised P&L"
                  value={`$${portfolio.total_unrealised_pnl?.toFixed(2) || '0.00'}`}
                  change={portfolio.total_unrealised_pnl}
                  icon="📊"
                />
              </div>
            )}

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <EquityCurve />
              <DrawdownChart />
            </div>

            {/* Risk Dashboard */}
            <RiskDashboard />

            {/* Positions */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Open Positions</h2>
              {positions.length === 0 ? (
                <p className="text-gray-500">No open positions</p>
              ) : (
                <PositionsTable positions={positions} />
              )}
            </div>

            {/* Orders */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Recent Orders</h2>
              {orders.length === 0 ? (
                <p className="text-gray-500">No orders</p>
              ) : (
                <OrdersTable orders={orders} />
              )}
            </div>

            {/* AI Decisions */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">AI Trading Decisions</h2>
              {aiDecisions.length === 0 ? (
                <p className="text-gray-500">No AI decisions yet</p>
              ) : (
                <AIDecisionsTable
                  decisions={aiDecisions}
                  onApprove={handleApproveDecision}
                  onReject={handleRejectDecision}
                  updatingDecisionId={updatingDecisionId}
                />
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
