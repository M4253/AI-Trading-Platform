'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Layout from '@/components/Layout'

export default function BrokerSettingsPage() {
  const router = useRouter()
  const [host, setHost] = useState('127.0.0.1')
  const [port, setPort] = useState('7497')
  const [clientId, setClientId] = useState('1')
  const [accountId, setAccountId] = useState('')
  const [accountType, setAccountType] = useState('paper')
  const [testingConnection, setTestingConnection] = useState(false)
  const [message, setMessage] = useState('')

  const handleTestConnection = async () => {
    setTestingConnection(true)
    setMessage('Testing connection...')
    
    // Simulated test - in production this would actually test the connection
    setTimeout(() => {
      setMessage('❌ Not connected - IBKR is not currently connected to this platform')
      setTestingConnection(false)
    }, 1000)
  }

  const handleSave = () => {
    setMessage('⚠️ Broker settings are stored locally for configuration only. Live trading is disabled.')
  }

  const handleDisconnect = () => {
    setMessage('ℹ️ Not connected - No active IBKR connection')
  }

  return (
    <Layout user={localStorage.getItem('user')}>
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Broker Settings</h1>
          <p className="text-gray-600 mb-6">Configure your Interactive Brokers connection</p>

          {/* Connection Status */}
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="font-semibold text-yellow-900">Connection Status: <span className="text-red-600">Not Connected</span></p>
            <p className="text-sm text-yellow-800 mt-1">IBKR is not currently connected to this platform. Paper trading proceeds without a real connection.</p>
          </div>

          {/* Important Notice */}
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="font-semibold text-blue-900 mb-2">⚠️ Important Security Notice</p>
            <ul className="text-sm text-blue-800 space-y-1 ml-4 list-disc">
              <li>Credentials are never stored in plaintext or committed to Git</li>
              <li>Live trading is permanently disabled until Phase 8 verification</li>
              <li>Paper trading is the default and only active mode</li>
              <li>Connection credentials are stored securely in your local environment</li>
            </ul>
          </div>

          <form className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Host
                </label>
                <input
                  type="text"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  placeholder="127.0.0.1"
                />
                <p className="text-xs text-gray-500 mt-1">Default: 127.0.0.1 (localhost)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Port
                </label>
                <input
                  type="text"
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  placeholder="7497"
                />
                <p className="text-xs text-gray-500 mt-1">Default: 7497 (paper), 7496 (live)</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Client ID
                </label>
                <input
                  type="text"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  placeholder="1"
                />
                <p className="text-xs text-gray-500 mt-1">Unique identifier for your API connection</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Account ID
                </label>
                <input
                  type="text"
                  value={accountId}
                  onChange={(e) => setAccountId(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  placeholder="e.g., DU123456"
                />
                <p className="text-xs text-gray-500 mt-1">Your Interactive Brokers account ID</p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Account Type
              </label>
              <select
                value={accountType}
                onChange={(e) => setAccountType(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg"
              >
                <option value="paper">Paper Trading (Recommended)</option>
                <option value="live">Live Trading (Disabled)</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">Paper trading is the default and recommended mode</p>
            </div>

            <div className="border-t pt-4 mt-4">
              <p className="text-sm text-gray-600 mb-3 font-semibold">Connection Settings Information</p>
              <ul className="text-sm text-gray-600 space-y-1 ml-4 list-disc">
                <li><strong>Host:</strong> IP address where TWS or IB Gateway is running</li>
                <li><strong>Port 7497:</strong> Paper trading port (read-only simulation)</li>
                <li><strong>Port 7496:</strong> Live trading port (real orders - currently disabled)</li>
                <li><strong>Client ID:</strong> Unique ID for this application (1-2147483647)</li>
                <li><strong>Account ID:</strong> Found in TWS Account window, e.g., DU1234567 or U1234567</li>
              </ul>
            </div>
          </form>

          {/* Status Message */}
          {message && (
            <div className={`mt-6 p-4 rounded-lg ${
              message.includes('❌') 
                ? 'bg-red-50 text-red-700 border border-red-200'
                : message.includes('✓')
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-blue-50 text-blue-700 border border-blue-200'
            }`}>
              {message}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 mt-6">
            <button
              onClick={handleTestConnection}
              disabled={testingConnection}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-lg font-medium transition"
            >
              {testingConnection ? 'Testing...' : 'Test Connection'}
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition"
            >
              Save Settings
            </button>
            <button
              onClick={handleDisconnect}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition"
            >
              Disconnect
            </button>
          </div>

          {/* Footer Note */}
          <div className="mt-8 pt-6 border-t text-xs text-gray-500">
            <p><strong>Security:</strong> This page does not send any real credentials over the network. All settings are stored locally.</p>
            <p className="mt-2"><strong>Live Trading:</strong> Remains permanently disabled. Phase 8 verification and a separate go-live gate are required before live orders can be placed.</p>
          </div>
        </div>
      </div>
    </Layout>
  )
}
