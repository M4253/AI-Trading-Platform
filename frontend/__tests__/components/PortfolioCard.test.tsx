import React from 'react'
import { render, screen } from '@testing-library/react'
import PortfolioCard from '@/components/PortfolioCard'

describe('PortfolioCard', () => {
  it('renders title and value', () => {
    render(
      <PortfolioCard
        title="Account Equity"
        value="$100,000.00"
        icon="💰"
      />
    )
    
    expect(screen.getByText('Account Equity')).toBeInTheDocument()
    expect(screen.getByText('$100,000.00')).toBeInTheDocument()
  })

  it('displays positive change in green', () => {
    render(
      <PortfolioCard
        title="Profit"
        value="$50,000"
        change={5000}
      />
    )
    
    const changeElement = screen.getByText('+5000.00')
    expect(changeElement).toHaveClass('text-green-600')
  })

  it('displays negative change in red', () => {
    render(
      <PortfolioCard
        title="Loss"
        value="$50,000"
        change={-2000}
      />
    )
    
    const changeElement = screen.getByText('-2000.00')
    expect(changeElement).toHaveClass('text-red-600')
  })
})
