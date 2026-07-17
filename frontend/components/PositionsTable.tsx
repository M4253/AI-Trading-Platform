'use client'

import React from 'react'

interface Position {
  symbol: string
  qty: number
  avg_entry_price: number
  current_price: number
  unrealised_pnl: number
}

interface PositionsTableProps {
  positions: Position[]
}

export default function PositionsTable({ positions }: PositionsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Qty</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entry Price</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Current Price</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Unrealised P&L</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {positions.map((pos) => (
            <tr key={pos.symbol} className="hover:bg-gray-50">
              <td className="px-6 py-4 text-sm font-medium text-gray-900">{pos.symbol}</td>
              <td className="px-6 py-4 text-sm text-gray-600">{pos.qty}</td>
              <td className="px-6 py-4 text-sm text-gray-600">${pos.avg_entry_price.toFixed(2)}</td>
              <td className="px-6 py-4 text-sm text-gray-600">${pos.current_price.toFixed(2)}</td>
              <td className={`px-6 py-4 text-sm font-semibold ${pos.unrealised_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${pos.unrealised_pnl.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
