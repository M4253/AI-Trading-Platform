import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import AIDecisionsTable from '@/components/AIDecisionsTable'

describe('AIDecisionsTable', () => {
  it('displays persisted reasoning, confidence, and paper approval controls', () => {
    const onApprove = jest.fn()
    const onReject = jest.fn()
    render(
      <AIDecisionsTable
        decisions={[{
          id: 'decision-1',
          symbol: 'AAPL',
          proposed_action: 'BUY',
          proposed_side: 'buy',
          proposed_qty: 2,
          confidence_score: 82,
          opportunity_score: 71,
          risk_score: 24,
          rationale: 'Chart momentum is positive.\nNews sentiment is constructive.',
          timestamp: '2026-07-17T10:00:00Z',
          decision_status: 'awaiting_approval',
          execution_status: 'pending_approval',
          outcome: 'manual_approval_required',
        }]}
        onApprove={onApprove}
        onReject={onReject}
      />,
    )

    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('82%')).toBeInTheDocument()
    expect(screen.getByText('manual_approval_required')).toBeInTheDocument()
    expect(screen.getByText(/Chart momentum is positive/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Approve Paper' }))
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
    expect(onApprove).toHaveBeenCalledWith('decision-1')
    expect(onReject).toHaveBeenCalledWith('decision-1')
  })
})
