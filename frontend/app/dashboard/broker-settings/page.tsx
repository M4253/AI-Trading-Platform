'use client'

import React, { FormEvent, useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import API, { getSessionValue } from '@/lib/api'

type BrokerMode = 'paper' | 'live'
type BrokerStatus = 'disconnected' | 'paper_ready' | 'live_locked'

interface BrokerConfiguration {
  id: string
  name: string
  broker: 'interactive_brokers'
  mode: BrokerMode
  host: string
  port: number
  client_id: number
  profile_label: string
  status: BrokerStatus
  last_mock_tested_at: string | null
}

interface BrokerDraft {
  name: string
  mode: BrokerMode
  host: string
  port: string
  clientId: string
  profileLabel: string
}

const emptyDraft = (): BrokerDraft => ({
  name: 'Interactive Brokers Paper',
  mode: 'paper',
  host: '127.0.0.1',
  port: '7497',
  clientId: '1',
  profileLabel: '',
})

const statusDetails: Record<BrokerStatus, { label: string; className: string }> = {
  disconnected: {
    label: 'Disconnected',
    className: 'bg-gray-100 text-gray-800 border-gray-300',
  },
  paper_ready: {
    label: 'Paper Ready',
    className: 'bg-green-100 text-green-800 border-green-300',
  },
  live_locked: {
    label: 'Live Locked',
    className: 'bg-red-100 text-red-800 border-red-300',
  },
}

export default function BrokerSettingsPage() {
  const [configurations, setConfigurations] = useState<BrokerConfiguration[]>([])
  const [draft, setDraft] = useState<BrokerDraft>(emptyDraft)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [user, setUser] = useState<string | null>(null)

  useEffect(() => {
    setUser(getSessionValue('user'))
    void loadConfigurations()
  }, [])

  async function loadConfigurations() {
    try {
      setLoading(true)
      const response = await API.get('/broker-configurations')
      setConfigurations(response.data.configurations || [])
      setError('')
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to load broker configurations')
    } finally {
      setLoading(false)
    }
  }

  function updateDraft<K extends keyof BrokerDraft>(field: K, value: BrokerDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  function resetForm() {
    setDraft(emptyDraft())
    setEditingId(null)
  }

  async function saveConfiguration(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    setError('')

    const payload = {
      name: draft.name,
      broker: 'interactive_brokers' as const,
      mode: draft.mode,
      host: draft.host,
      port: Number(draft.port),
      client_id: Number(draft.clientId),
      profile_label: draft.profileLabel,
    }

    try {
      if (editingId) {
        await API.put(`/broker-configurations/${editingId}`, payload)
        setMessage('Broker configuration saved. It remains disconnected.')
      } else {
        await API.post('/broker-configurations', payload)
        setMessage('Broker configuration added. It remains disconnected.')
      }
      resetForm()
      await loadConfigurations()
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to save broker configuration')
    } finally {
      setSaving(false)
    }
  }

  function editConfiguration(configuration: BrokerConfiguration) {
    setDraft({
      name: configuration.name,
      mode: configuration.mode,
      host: configuration.host,
      port: String(configuration.port),
      clientId: String(configuration.client_id),
      profileLabel: configuration.profile_label || '',
    })
    setEditingId(configuration.id)
    setMessage('')
    setError('')
  }

  async function removeConfiguration(configId: string) {
    if (!window.confirm('Remove this local broker configuration?')) return

    try {
      await API.delete(`/broker-configurations/${configId}`)
      if (editingId === configId) resetForm()
      setMessage('Broker configuration removed.')
      await loadConfigurations()
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to remove broker configuration')
    }
  }

  async function runMockTest(configId: string) {
    try {
      setMessage('')
      const response = await API.post(`/broker-configurations/${configId}/test`)
      setMessage(response.data.message)
      await loadConfigurations()
    } catch (requestError: any) {
      setError(requestError.response?.data?.detail || 'Unable to run mock connection test')
    }
  }

  const hasPaperReadyConfiguration = configurations.some(
    (configuration) => configuration.status === 'paper_ready',
  )

  return (
    <Layout user={user}>
      <div className="mx-auto max-w-5xl space-y-6">
        <section className="rounded-lg bg-white p-6 shadow">
          <h1 className="text-2xl font-bold text-gray-900">Broker Settings</h1>
          <p className="mt-2 text-gray-600">Manage local Interactive Brokers profiles for future paper-trading use.</p>

          <div className="mt-6 grid gap-4 md:grid-cols-3" aria-label="Broker safety status">
            <div className="rounded-lg border border-gray-300 bg-gray-50 p-4">
              <p className="text-sm font-medium text-gray-600">Broker Connection</p>
              <p className="mt-1 text-lg font-bold text-gray-900">Disconnected</p>
              <p className="mt-1 text-xs text-gray-600">No network broker connection is available.</p>
            </div>
            <div className="rounded-lg border border-green-300 bg-green-50 p-4">
              <p className="text-sm font-medium text-green-700">Paper Ready</p>
              <p className="mt-1 text-lg font-bold text-green-900">{hasPaperReadyConfiguration ? 'Ready' : 'Not Tested'}</p>
              <p className="mt-1 text-xs text-green-800">Mock checks validate saved paper metadata only.</p>
            </div>
            <div className="rounded-lg border border-red-300 bg-red-50 p-4">
              <p className="text-sm font-medium text-red-700">Live Trading</p>
              <p className="mt-1 text-lg font-bold text-red-900">Live Locked</p>
              <p className="mt-1 text-xs text-red-800">Real IBKR verification has not been performed.</p>
            </div>
          </div>

          <div className="mt-6 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
            <p className="font-semibold">Credential-safe local storage</p>
            <p className="mt-1">Only non-secret connection metadata is saved locally. This page never asks for passwords, API keys, or account numbers, and mock testing never contacts IBKR.</p>
          </div>
        </section>

        <section className="rounded-lg bg-white p-6 shadow">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold text-gray-900">{editingId ? 'Edit Broker Configuration' : 'Add Broker Configuration'}</h2>
              <p className="mt-1 text-sm text-gray-600">Interactive Brokers is available as a saved, disconnected profile.</p>
            </div>
            {editingId && (
              <button type="button" onClick={resetForm} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                Cancel Edit
              </button>
            )}
          </div>

          <form onSubmit={saveConfiguration} className="mt-6 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block text-sm font-medium text-gray-700">
                Configuration Name
                <input value={draft.name} onChange={(event) => updateDraft('name', event.target.value)} required maxLength={80} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" placeholder="Interactive Brokers Paper" />
              </label>
              <label className="block text-sm font-medium text-gray-700">
                Broker
                <input value="Interactive Brokers" disabled className="mt-1 w-full cursor-not-allowed rounded-lg border border-gray-200 bg-gray-100 px-3 py-2 text-gray-600" />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="block text-sm font-medium text-gray-700">
                Host
                <input value={draft.host} onChange={(event) => updateDraft('host', event.target.value)} required maxLength={255} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" placeholder="127.0.0.1" />
              </label>
              <label className="block text-sm font-medium text-gray-700">
                Paper Port
                <input type="number" min="1" max="65535" value={draft.port} onChange={(event) => updateDraft('port', event.target.value)} required className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
              </label>
              <label className="block text-sm font-medium text-gray-700">
                Client ID
                <input type="number" min="1" max="2147483647" value={draft.clientId} onChange={(event) => updateDraft('clientId', event.target.value)} required className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block text-sm font-medium text-gray-700">
                Local Profile Label <span className="font-normal text-gray-500">(optional)</span>
                <input value={draft.profileLabel} onChange={(event) => updateDraft('profileLabel', event.target.value)} maxLength={120} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" placeholder="My paper workspace" />
              </label>
              <label className="block text-sm font-medium text-gray-700">
                Trading Mode
                <select value={draft.mode} onChange={(event) => updateDraft('mode', event.target.value as BrokerMode)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
                  <option value="paper">Paper Trading (Default)</option>
                  <option value="live">Live Trading (Locked)</option>
                </select>
                <span className="mt-1 block text-xs text-red-600">A live profile is saved as locked and cannot connect or place orders.</span>
              </label>
            </div>

            <button type="submit" disabled={saving} className="rounded-lg bg-blue-600 px-5 py-2 font-semibold text-white hover:bg-blue-700 disabled:bg-gray-400">
              {saving ? 'Saving…' : editingId ? 'Save Changes' : 'Add Configuration'}
            </button>
          </form>
        </section>

        <section className="rounded-lg bg-white p-6 shadow">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Saved Configurations</h2>
              <p className="mt-1 text-sm text-gray-600">Every configuration remains disconnected until a future, separately verified phase.</p>
            </div>
            <button type="button" onClick={() => void loadConfigurations()} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">Refresh</button>
          </div>

          {loading ? (
            <p className="py-8 text-center text-gray-500">Loading broker configurations…</p>
          ) : configurations.length === 0 ? (
            <p className="py-8 text-center text-gray-500">No broker configurations saved yet.</p>
          ) : (
            <div className="mt-5 space-y-3">
              {configurations.map((configuration) => {
                const status = statusDetails[configuration.status]
                return (
                  <article key={configuration.id} className="rounded-lg border border-gray-200 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold text-gray-900">{configuration.name}</h3>
                          <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${status.className}`}>{status.label}</span>
                        </div>
                        <p className="mt-1 text-sm text-gray-600">Interactive Brokers · {configuration.mode === 'paper' ? 'Paper' : 'Live (Locked)'} · {configuration.host}:{configuration.port} · Client {configuration.client_id}</p>
                        {configuration.profile_label && <p className="mt-1 text-sm text-gray-500">Local label: {configuration.profile_label}</p>}
                        {configuration.last_mock_tested_at && <p className="mt-1 text-xs text-gray-500">Last mock test: {new Date(configuration.last_mock_tested_at).toLocaleString()}</p>}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={() => void runMockTest(configuration.id)} className="rounded-lg bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700">Run Mock Test</button>
                        <button type="button" onClick={() => editConfiguration(configuration)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">Edit</button>
                        <button type="button" onClick={() => void removeConfiguration(configuration.id)} className="rounded-lg border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50">Remove</button>
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>

        {message && <div role="status" className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">{message}</div>}
        {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      </div>
    </Layout>
  )
}
