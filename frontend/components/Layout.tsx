'use client'

import React, { ReactNode } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { clearSession } from '@/lib/api'

interface LayoutProps {
  children: ReactNode
  user?: string | null
  onRefresh?: () => void
}

export default function Layout({ children, user, onRefresh }: LayoutProps) {
  const router = useRouter()

  const handleLogout = () => {
    clearSession()
    router.push('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white shadow sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center gap-8">
              <Link href="/dashboard" className="flex items-center gap-2">
                <span className="text-xl font-bold text-blue-600">📈 AI Trading</span>
              </Link>
              <div className="hidden md:flex gap-4">
                <Link href="/dashboard" className="px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600">
                  Dashboard
                </Link>
                <Link href="/dashboard/broker-settings" className="px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600">
                  Broker Settings
                </Link>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {onRefresh && (
                <button
                  onClick={onRefresh}
                  className="p-2 text-gray-600 hover:text-blue-600 transition"
                  title="Refresh data"
                >
                  🔄
                </button>
              )}
              {user && <span className="text-sm text-gray-600">{user}</span>}
              <button
                onClick={handleLogout}
                className="px-3 py-2 text-sm font-medium text-red-600 hover:text-red-700 transition"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 mt-12 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm">
            AI Trading Platform · Paper Trading Mode · IBKR Not Connected · Live Trading Disabled
          </p>
        </div>
      </footer>
    </div>
  )
}
