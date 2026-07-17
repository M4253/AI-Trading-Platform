'use client'

import React, { useEffect, useState } from 'react'
import API from '@/lib/api'

type ExecutionMode = 'manual_approval' | 'automatic_paper'

interface ModelOption {
  key: string
  display_name: string
  version: string
}

interface AIExecutionSettingsProps {
  onChanged?: () => void
}

export default function AIExecutionSettings({ onChanged }: AIExecutionSettingsProps) {
  const [executionMode, setExecutionMode] = useState<ExecutionMode>('manual_approval')
  const [modelKey, setModelKey] = useState('rule_based_v1')
  const [models, setModels] = useState<ModelOption[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadSettings() {
      try {
        const [settingsResponse, modelsResponse] = await Promise.all([
          API.get('/ai/settings'),
          API.get('/ai/models'),
        ])
        setExecutionMode(settingsResponse.data.execution_mode)
        setModelKey(settingsResponse.data.model_key)
        setModels(modelsResponse.data.models || [])
      } catch (requestError: any) {
        setError(requestError.response?.data?.detail || 'Unable to load AI execution settings')
      } finally {
        setLoading(false)
      }
    }
    void loadSettings()
  }, [])

  async function saveSettings() {
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const response = await API.patch('/ai/settings', {
        execution_mode: executionMode,
        model_key: modelKey,
      })
      setExecutionMode(response.data.execution_mode)
      setModelKey(response.data.model_key)
      setMessage(executionMode === 'automatic_paper'
        ? 'Automatic paper execution is enabled. Live trading remains locked.'
        : 'Manual approval is required before every paper order.')
      onChanged?.()
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to save AI execution settings')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-lg bg-white p-6 shadow" aria-labelledby="ai-execution-settings-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="ai-execution-settings-heading" className="text-xl font-bold text-gray-900">AI Decision Engine</h2>
          <p className="mt-1 text-sm text-gray-600">Choose how saved AI decisions move through the paper-trading workflow.</p>
        </div>
        <span className="rounded-full border border-red-300 bg-red-50 px-3 py-1 text-xs font-semibold text-red-800">Live Locked</span>
      </div>

      {loading ? <p className="mt-4 text-sm text-gray-500">Loading AI settings…</p> : (
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="ai-execution-policy" className="block text-sm font-medium text-gray-700">Execution policy</label>
            <select id="ai-execution-policy" value={executionMode} onChange={(event) => setExecutionMode(event.target.value as ExecutionMode)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
              <option value="manual_approval">Manual approval (default)</option>
              <option value="automatic_paper">Automatic paper execution</option>
            </select>
            <span className="mt-1 block text-xs text-gray-500">Automatic execution still uses the paper engine, lifecycle gates, and risk checks.</span>
          </div>
          <div>
            <label htmlFor="ai-decision-model" className="block text-sm font-medium text-gray-700">Decision model</label>
            <select id="ai-decision-model" value={modelKey} onChange={(event) => setModelKey(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
              {models.map((model) => <option key={model.key} value={model.key}>{model.display_name} (v{model.version})</option>)}
            </select>
            <span className="mt-1 block text-xs text-gray-500">Only registered local models are selectable. No API key or external model connection is configured.</span>
          </div>
        </div>
      )}

      <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
        The engine records supplied charts, indicators, news, market data, portfolio state, reasoning, confidence, and every paper-execution outcome. It never connects to a real broker.
      </div>

      <button type="button" onClick={() => void saveSettings()} disabled={loading || saving} className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-gray-400">
        {saving ? 'Saving…' : 'Save AI Settings'}
      </button>
      {message && <p role="status" className="mt-3 text-sm text-green-700">{message}</p>}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    </section>
  )
}
