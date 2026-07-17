'use client'

import React from 'react'

export default function RiskDashboard() {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Risk Monitoring</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="p-4 border border-gray-200 rounded-lg">
          <p className="text-sm text-gray-600 font-medium">Max Daily Loss</p>
          <p className="text-2xl font-bold text-green-600 mt-1">$5,000</p>
          <p className="text-xs text-gray-500 mt-1">Status: ✓ OK</p>
        </div>
        <div className="p-4 border border-gray-200 rounded-lg">
          <p className="text-sm text-gray-600 font-medium">Max Drawdown</p>
          <p className="text-2xl font-bold text-green-600 mt-1">15%</p>
          <p className="text-xs text-gray-500 mt-1">Status: ✓ OK</p>
        </div>
        <div className="p-4 border border-gray-200 rounded-lg">
          <p className="text-sm text-gray-600 font-medium">Max Position Size</p>
          <p className="text-2xl font-bold text-green-600 mt-1">$25,000</p>
          <p className="text-xs text-gray-500 mt-1">Status: ✓ OK</p>
        </div>
      </div>
      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 text-blue-700 text-sm rounded">
        Paper-only guardrails are enforced by the backend. Trading stays stopped until you explicitly start paper trading.
      </div>
    </div>
  )
}
