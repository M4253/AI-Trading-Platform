'use client'

import React from 'react'

interface PortfolioCardProps {
  title: string
  value: string | number
  change?: number
  icon?: string
}

export default function PortfolioCard({ title, value, change, icon }: PortfolioCardProps) {
  const isPositive = change ? change >= 0 : false

  return (
    <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-600 font-medium">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-2">{value}</p>
          {change !== undefined && (
            <p className={`text-sm font-semibold mt-2 ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
              {isPositive ? '+' : ''}{typeof change === 'number' ? change.toFixed(2) : change}
            </p>
          )}
        </div>
        {icon && <span className="text-3xl">{icon}</span>}
      </div>
    </div>
  )
}
