'use client'

import React from 'react'

interface Decision {
  id: string
  symbol: string
  side: string
  proposed_qty: number
  confidence: number
  opportunity: number
  risk: number
  rationale: string
  created_at: string
}

interface AIDecisionsTableProps {
  decisions: Decision[]
}

export default function AIDecisionsTable({ decisions }: AIDecisionsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Side</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Opportunity</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Risk</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {decisions.map((decision) => (
            <tr key={decision.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 text-sm font-medium text-gray-900">{decision.symbol}</td>
              <td className="px-6 py-4 text-sm">
                <span className={`px-2 py-1 rounded text-xs font-semibold ${decision.side === 'buy' ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800'}`}>
                  {decision.side.toUpperCase()}
                </span>
              </td>
              <td className="px-6 py-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-16 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-blue-600 h-2 rounded-full" 
                      style={{ width: `${decision.confidence * 100}%` }}
                    ></div>
                  </div>
                  <span className="text-xs font-semibold text-gray-700">{(decision.confidence * 100).toFixed(0)}%</span>
                </div>
              </td>
              <td className="px-6 py-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-16 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-green-600 h-2 rounded-full" 
                      style={{ width: `${decision.opportunity * 100}%` }}
                    ></div>
                  </div>
                  <span className="text-xs font-semibold text-gray-700">{(decision.opportunity * 100).toFixed(0)}%</span>
                </div>
              </td>
              <td className="px-6 py-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-16 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-red-600 h-2 rounded-full" 
                      style={{ width: `${decision.risk * 100}%` }}
                    ></div>
                  </div>
                  <span className="text-xs font-semibold text-gray-700">{(decision.risk * 100).toFixed(0)}%</span>
                </div>
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">
                {new Date(decision.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
