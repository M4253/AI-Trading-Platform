'use client'

import React from 'react'

interface TradingControlsProps {
  status: string
  onStart: () => void
  onPause: () => void
  onStop: () => void
}

export default function TradingControls({ status, onStart, onPause, onStop }: TradingControlsProps) {
  const getStatusColor = () => {
    switch (status) {
      case 'running':
        return 'bg-green-100 text-green-800 border-green-300'
      case 'paused':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300'
      case 'stopped':
        return 'bg-red-100 text-red-800 border-red-300'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300'
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Paper Trading Control</h2>
          <div className={`inline-block px-4 py-2 rounded-lg border font-semibold text-sm ${getStatusColor()}`}>
            Status: {status.toUpperCase()}
          </div>
        </div>

        <div className="flex gap-3 flex-wrap">
          {status !== 'running' && (
            <button
              onClick={onStart}
              className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition"
            >
              ▶️ Start Trading
            </button>
          )}

          {status !== 'paused' && status === 'running' && (
            <button
              onClick={onPause}
              className="px-6 py-2 bg-yellow-600 hover:bg-yellow-700 text-white font-semibold rounded-lg transition"
            >
              ⏸ Pause Trading
            </button>
          )}

          {status === 'paused' && (
            <button
              onClick={onStart}
              className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition"
            >
              ▶️ Resume Trading
            </button>
          )}

          <button
            onClick={onStop}
            className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition border-2 border-red-800"
          >
            🛑 STOP ALL TRADING
          </button>
        </div>
      </div>

      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 text-blue-700 text-sm rounded">
        ℹ️ Stop All Trading immediately blocks new orders but does not automatically liquidate existing positions.
      </div>
    </div>
  )
}
