'use client'

import React, { FormEvent, useEffect, useMemo, useState } from 'react'
import API from '@/lib/api'

interface Watchlist {
  id: string
  name: string
  symbols: string[]
}

interface MarketIntelligencePanelProps {
  onDecisionCreated?: () => void
}

export default function MarketIntelligencePanel({ onDecisionCreated }: MarketIntelligencePanelProps) {
  const [health, setHealth] = useState<any>(null)
  const [watchlists, setWatchlists] = useState<Watchlist[]>([])
  const [selectedWatchlistId, setSelectedWatchlistId] = useState('')
  const [newWatchlistName, setNewWatchlistName] = useState('')
  const [watchlistName, setWatchlistName] = useState('')
  const [newSymbol, setNewSymbol] = useState('')
  const [context, setContext] = useState<any>(null)
  const [scanResults, setScanResults] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const selectedWatchlist = useMemo(
    () => watchlists.find((watchlist) => watchlist.id === selectedWatchlistId) || watchlists[0],
    [selectedWatchlistId, watchlists],
  )

  async function loadOverview() {
    try {
      setLoading(true)
      const [healthResponse, watchlistsResponse] = await Promise.all([
        API.get('/market/health'),
        API.get('/market/watchlists'),
      ])
      const loadedWatchlists = watchlistsResponse.data.watchlists || []
      setHealth(healthResponse.data)
      setWatchlists(loadedWatchlists)
      setSelectedWatchlistId((current) => current || loadedWatchlists[0]?.id || '')
      setError('')
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to load market intelligence')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadOverview()
  }, [])

  useEffect(() => {
    setWatchlistName(selectedWatchlist?.name || '')
  }, [selectedWatchlist?.id, selectedWatchlist?.name])

  async function createWatchlist(event: FormEvent) {
    event.preventDefault()
    if (!newWatchlistName.trim()) return
    try {
      setWorking(true)
      const response = await API.post('/market/watchlists', { name: newWatchlistName })
      setWatchlists((current) => [...current, response.data])
      setSelectedWatchlistId(response.data.id)
      setNewWatchlistName('')
      setMessage('Watchlist created locally.')
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to create watchlist')
    } finally {
      setWorking(false)
    }
  }

  async function addSymbol(event: FormEvent) {
    event.preventDefault()
    if (!selectedWatchlist || !newSymbol.trim()) return
    try {
      setWorking(true)
      const response = await API.post(`/market/watchlists/${selectedWatchlist.id}/symbols`, { symbol: newSymbol })
      setWatchlists((current) => current.map((watchlist) => watchlist.id === response.data.id ? response.data : watchlist))
      setNewSymbol('')
      setMessage('Symbol added to the watchlist.')
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to add symbol')
    } finally {
      setWorking(false)
    }
  }

  async function renameWatchlist(event: FormEvent) {
    event.preventDefault()
    if (!selectedWatchlist || !watchlistName.trim()) return
    try {
      setWorking(true)
      const response = await API.put(`/market/watchlists/${selectedWatchlist.id}`, { name: watchlistName })
      setWatchlists((current) => current.map((watchlist) => watchlist.id === response.data.id ? response.data : watchlist))
      setMessage('Watchlist renamed.')
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to rename watchlist')
    } finally {
      setWorking(false)
    }
  }

  async function deleteWatchlist() {
    if (!selectedWatchlist || !window.confirm(`Remove watchlist “${selectedWatchlist.name}”?`)) return
    try {
      setWorking(true)
      await API.delete(`/market/watchlists/${selectedWatchlist.id}`)
      setWatchlists((current) => current.filter((watchlist) => watchlist.id !== selectedWatchlist.id))
      setSelectedWatchlistId('')
      setContext(null)
      setScanResults([])
      setMessage('Watchlist removed.')
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to remove watchlist')
    } finally {
      setWorking(false)
    }
  }

  async function removeSymbol(symbol: string) {
    if (!selectedWatchlist) return
    try {
      setWorking(true)
      const response = await API.delete(`/market/watchlists/${selectedWatchlist.id}/symbols/${symbol}`)
      setWatchlists((current) => current.map((watchlist) => watchlist.id === response.data.id ? response.data : watchlist))
      if (context?.symbol === symbol) setContext(null)
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to remove symbol')
    } finally {
      setWorking(false)
    }
  }

  async function loadContext(symbol: string) {
    try {
      setWorking(true)
      setMessage('')
      const response = await API.get(`/market/context/${symbol}`)
      setContext(response.data)
      setMessage(`${symbol} market context loaded.`)
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to load market context')
    } finally {
      setWorking(false)
    }
  }

  async function scanWatchlist() {
    if (!selectedWatchlist) return
    try {
      setWorking(true)
      const response = await API.post('/market/scanner', { watchlist_id: selectedWatchlist.id })
      setScanResults(response.data.results || [])
      setMessage(`Scanned ${response.data.count || 0} symbol(s).`)
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to run market scanner')
    } finally {
      setWorking(false)
    }
  }

  async function createAIDecision() {
    if (!context?.symbol) return
    try {
      setWorking(true)
      const response = await API.post(`/market/ai-decisions/${context.symbol}`)
      setMessage(`AI decision recorded for ${context.symbol}: ${response.data.decision.proposed_action}.`)
      onDecisionCreated?.()
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to create an AI market decision')
    } finally {
      setWorking(false)
    }
  }

  return (
    <section className="rounded-lg bg-white p-6 shadow" aria-labelledby="market-intelligence-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="market-intelligence-heading" className="text-xl font-bold text-gray-900">Market Intelligence</h2>
          <p className="mt-1 text-sm text-gray-600">Public market data, financial-news sentiment, economic events, and scanner context for paper-only AI decisions.</p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${health?.status === 'healthy' ? 'border-green-300 bg-green-50 text-green-800' : 'border-amber-300 bg-amber-50 text-amber-800'}`}>
          Market Health: {health?.status || 'Loading'}
        </span>
      </div>

      <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
        No paid API, API key, broker account, or real broker connection is required. Public providers fall back to local deterministic context when unavailable, and the fallback state is shown in market health.
      </div>

      {loading ? <p className="mt-5 text-sm text-gray-500">Loading market intelligence…</p> : (
        <>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {(health?.providers || []).map((provider: any) => (
              <div key={`${provider.category}-${provider.name}`} className="rounded border border-gray-200 p-3 text-sm">
                <p className="font-semibold text-gray-900">{provider.name}</p>
                <p className="text-xs text-gray-500">{provider.category.replace('_', ' ')} · {provider.is_free ? 'No-key public' : 'Configured'}</p>
                <p className={`mt-1 text-xs font-medium ${provider.status === 'unavailable' ? 'text-amber-700' : 'text-green-700'}`}>{provider.status.replace('_', ' ')}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            <div className="rounded-lg border border-gray-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-bold text-gray-900">Watchlists & Symbols</h3>
                <button type="button" onClick={() => void loadOverview()} className="text-sm font-medium text-blue-700 hover:underline">Refresh</button>
              </div>
              <label htmlFor="market-watchlist" className="mt-3 block text-sm font-medium text-gray-700">Active watchlist</label>
              <select id="market-watchlist" value={selectedWatchlist?.id || ''} onChange={(event) => setSelectedWatchlistId(event.target.value)} className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm">
                {watchlists.map((watchlist) => <option key={watchlist.id} value={watchlist.id}>{watchlist.name}</option>)}
              </select>
              <form onSubmit={renameWatchlist} className="mt-3 flex gap-2">
                <input aria-label="Active watchlist name" value={watchlistName} onChange={(event) => setWatchlistName(event.target.value)} maxLength={80} className="min-w-0 flex-1 rounded border border-gray-300 px-3 py-2 text-sm" />
                <button disabled={working || !selectedWatchlist} type="submit" className="rounded border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:text-gray-400">Rename</button>
                <button disabled={working || !selectedWatchlist} type="button" onClick={() => void deleteWatchlist()} className="rounded border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:text-gray-400">Delete</button>
              </form>
              <form onSubmit={createWatchlist} className="mt-3 flex gap-2">
                <input aria-label="New watchlist name" value={newWatchlistName} onChange={(event) => setNewWatchlistName(event.target.value)} maxLength={80} placeholder="New watchlist" className="min-w-0 flex-1 rounded border border-gray-300 px-3 py-2 text-sm" />
                <button disabled={working} type="submit" className="rounded border border-blue-300 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:text-gray-400">Add list</button>
              </form>
              <form onSubmit={addSymbol} className="mt-3 flex gap-2">
                <input aria-label="Symbol to add" value={newSymbol} onChange={(event) => setNewSymbol(event.target.value.toUpperCase())} maxLength={15} placeholder="AAPL" className="min-w-0 flex-1 rounded border border-gray-300 px-3 py-2 text-sm" />
                <button disabled={working || !selectedWatchlist} type="submit" className="rounded bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-gray-400">Add symbol</button>
              </form>
              <div className="mt-3 flex flex-wrap gap-2">
                {(selectedWatchlist?.symbols || []).length === 0 ? <p className="text-sm text-gray-500">Add symbols to scan public market context.</p> : selectedWatchlist?.symbols.map((symbol) => (
                  <span key={symbol} className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-1 text-sm text-gray-800">
                    <button type="button" onClick={() => void loadContext(symbol)} className="font-semibold hover:text-blue-700">{symbol}</button>
                    <button type="button" aria-label={`Remove ${symbol}`} onClick={() => void removeSymbol(symbol)} className="text-gray-500 hover:text-red-700">×</button>
                  </span>
                ))}
              </div>
              <button type="button" disabled={working || !(selectedWatchlist?.symbols || []).length} onClick={() => void scanWatchlist()} className="mt-4 rounded bg-slate-700 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:bg-gray-400">Run Market Scanner</button>
            </div>

            <div className="rounded-lg border border-gray-200 p-4">
              <h3 className="font-bold text-gray-900">AI Market Context</h3>
              {!context ? <p className="mt-3 text-sm text-gray-500">Select a symbol to inspect chart signals, news sentiment, economic events, and the AI-ready market context.</p> : (
                <div className="mt-3 space-y-2 text-sm text-gray-700">
                  <p><span className="font-semibold">{context.symbol}</span> · ${Number(context.quote.price).toFixed(2)} · {Number(context.quote.change_pct).toFixed(2)}%</p>
                  <p>Trend {Number(context.indicators.trend_score).toFixed(2)} · RSI {Number(context.indicators.rsi).toFixed(0)} · News {context.news_sentiment.label} ({Number(context.news_sentiment.score).toFixed(2)})</p>
                  <p>Economic events: {context.economic_calendar.events.length} · Source: {context.market_health.market_data_provider}{context.market_health.is_fallback ? ' (local fallback)' : ''}</p>
                  <button type="button" disabled={working} onClick={() => void createAIDecision()} className="rounded bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:bg-gray-400">Create AI Paper Decision</button>
                </div>
              )}
            </div>
          </div>

          {scanResults.length > 0 && <div className="mt-5 rounded-lg border border-gray-200 p-4">
            <h3 className="font-bold text-gray-900">Scanner Results</h3>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs uppercase text-gray-500"><tr><th className="pr-4">Symbol</th><th className="pr-4">Price</th><th className="pr-4">Trend</th><th className="pr-4">News</th><th>Score</th></tr></thead>
                <tbody>{scanResults.map((result) => <tr key={result.symbol} className="border-t border-gray-100"><td className="py-2 font-semibold">{result.symbol}</td><td>${Number(result.price || 0).toFixed(2)}</td><td>{Number(result.trend_score || 0).toFixed(2)}</td><td>{Number(result.news_sentiment || 0).toFixed(2)}</td><td className="font-semibold">{result.error || Number(result.scanner_score || 0).toFixed(0)}</td></tr>)}</tbody>
              </table>
            </div>
          </div>}
        </>
      )}
      {message && <p role="status" className="mt-4 text-sm text-green-700">{message}</p>}
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
    </section>
  )
}
