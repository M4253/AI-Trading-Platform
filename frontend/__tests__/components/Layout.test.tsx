import React from 'react'
import { render, screen } from '@testing-library/react'

// Mock next/link and next/navigation
jest.mock('next/link', () => {
  return ({ children, href }: any) => <a href={href}>{children}</a>
})

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}))

import Layout from '@/components/Layout'

describe('Layout', () => {
  it('displays user name', () => {
    render(
      <Layout user="testuser@example.com">
        <div>Test content</div>
      </Layout>
    )
    
    expect(screen.getByText('testuser@example.com')).toBeInTheDocument()
  })

  it('renders children', () => {
    render(
      <Layout user="user@example.com">
        <div>Test content</div>
      </Layout>
    )
    
    expect(screen.getByText('Test content')).toBeInTheDocument()
  })

  it('displays footer message', () => {
    render(
      <Layout user="user@example.com">
        <div>Test</div>
      </Layout>
    )
    
    expect(screen.getByText(/Paper Trading Mode/)).toBeInTheDocument()
    expect(screen.getByText(/IBKR Not Connected/)).toBeInTheDocument()
  })
})
