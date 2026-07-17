'use client'

import React, { useEffect, useState } from 'react'
import Layout from '@/components/Layout'

export default function BrokerSettingsPage() {
  const [host, setHost] = useState('127.0.0.1')
  const [port, setPort] = useState('7497')
  const [clientId, setClientId] = useState('1')
  const [accountId, setAccountId] = useState('')
  const [message, setMessage] = useState('')
  const [user, setUser] = useState<string | null>(null)

  useEffect(() => {
    setUser(localStorage.getItem('user'))
  }, [])

  const handleTestConnection = async () => {
    setMessage('Connection testing is disabled. No request was sent to IBKR.')
  }

  const handleSave = () => {
    setMessage('⚠️ Settings are display-only while broker integration is disabled. Nothing was saved or sent.')
  }

  const handleDisconnect = () => {
    setMessage('ℹ️ Not connected - No active IBKR connection')
  }

  return (
    <Layout user={user}>
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
              <li>No broker credentials are requested, stored, or sent by this page</li>
              <li>Live trading is disabled; real IBKR verification has not occurred</li>
              <li>Paper trading is the default and only active mode</li>
              <li>IBKR remains disconnected regardless of the values shown below</li>
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
                <p className="text-xs text-gray-500 mt-1">Default paper port: 7497</p>
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

            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
              <p className="font-medium text-blue-900">Account Type: Paper Trading Only</p>
              <p className="mt-1 text-xs text-blue-800">Live account selection is intentionally unavailable.</p>
            </div>

            <div className="border-t pt-4 mt-4">
              <p className="text-sm text-gray-600 mb-3 font-semibold">Connection Settings Information</p>
              <ul className="text-sm text-gray-600 space-y-1 ml-4 list-disc">
                <li><strong>Host:</strong> IP address where TWS or IB Gateway is running</li>
                <li><strong>Port 7497:</strong> Common IBKR paper port; this application will not connect to it</li>
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
              type="button"
              onClick={handleTestConnection}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition"
            >
              Test Connection
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition"
            >
              Save Settings
            </button>
            <button
              type="button"
              onClick={handleDisconnect}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition"
            >
              Disconnect
            </button>
          </div>

          {/* Footer Note */}
          <div className="mt-8 pt-6 border-t text-xs text-gray-500">
            <p><strong>Security:</strong> This page does not send real credentials or initiate a broker connection.</p>
            <p className="mt-2"><strong>Live Trading:</strong> Disabled. No real IBKR verification has been performed.</p>
          </div>
        </div>
      </div>
    </Layout>
  )
}
