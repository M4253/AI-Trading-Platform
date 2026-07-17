'use client'

import React from 'react'

interface Decision {
  id: string
  symbol: string
  side?: string | null
  proposed_side?: string | null
  proposed_action?: string
  proposed_qty?: number
  confidence?: number
  confidence_score?: number
  opportunity?: number
  opportunity_score?: number
  risk?: number
  risk_score?: number
  rationale?: string
  reasoning?: string[]
  created_at?: string
  timestamp?: string
  decision_status?: string
  execution_status?: string
  outcome?: string
}

interface AIDecisionsTableProps {
  decisions: Decision[]
  onApprove?: (decisionId: string) => void
  onReject?: (decisionId: string) => void
  updatingDecisionId?: string | null
}

function scorePercent(value: number | undefined) {
  const raw = Number(value || 0)
  const percent = raw <= 1 ? raw * 100 : raw
  return Math.max(0, Math.min(100, percent))
}

function Score({ value, color }: { value: number | undefined; color: string }) {
  const percent = scorePercent(value)
  return (
    <div className="flex min-w-[105px] items-center gap-2" aria-label={`${percent.toFixed(0)} percent`}>
      <div className="h-2 w-16 rounded-full bg-gray-200">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-700">{percent.toFixed(0)}%</span>
    </div>
  )
}

export default function AIDecisionsTable({
  decisions,
  onApprove,
  onReject,
  updatingDecisionId,
}: AIDecisionsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Symbol</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Decision</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Status</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Confidence</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Opportunity</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Risk</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Reasoning</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Time</th>
            {(onApprove || onReject) && <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Review</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {decisions.map((decision) => {
            const side = decision.proposed_side || decision.side
            const action = decision.proposed_action || (side ? side.toUpperCase() : 'HOLD')
            const pending = decision.execution_status === 'pending_approval'
            const isUpdating = updatingDecisionId === decision.id
            const rationale = decision.rationale || decision.reasoning?.join('\n') || 'No reasoning recorded.'
            const timestamp = decision.timestamp || decision.created_at

            return (
              <tr key={decision.id} className="hover:bg-gray-50">
                <td className="px-4 py-4 text-sm font-medium text-gray-900">{decision.symbol}</td>
                <td className="px-4 py-4 text-sm">
                  <span className={`rounded px-2 py-1 text-xs font-semibold ${side === 'buy' ? 'bg-blue-100 text-blue-800' : side === 'sell' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700'}`}>
                    {action}
                  </span>
                  {decision.proposed_qty ? <span className="ml-1 text-xs text-gray-500">{decision.proposed_qty}</span> : null}
                </td>
                <td className="px-4 py-4 text-xs text-gray-700">
                  <span className="rounded bg-gray-100 px-2 py-1 font-medium">{decision.outcome || decision.decision_status || 'recorded'}</span>
                </td>
                <td className="px-4 py-4 text-sm"><Score value={decision.confidence_score ?? decision.confidence} color="bg-blue-600" /></td>
                <td className="px-4 py-4 text-sm"><Score value={decision.opportunity_score ?? decision.opportunity} color="bg-green-600" /></td>
                <td className="px-4 py-4 text-sm"><Score value={decision.risk_score ?? decision.risk} color="bg-red-600" /></td>
                <td className="max-w-xs px-4 py-4 text-sm text-gray-600">
                  <details>
                    <summary className="cursor-pointer font-medium text-blue-700">View reasoning</summary>
                    <p className="mt-2 whitespace-pre-line text-xs leading-5">{rationale}</p>
                  </details>
                </td>
                <td className="px-4 py-4 text-sm text-gray-500">{timestamp ? new Date(timestamp).toLocaleString() : '—'}</td>
                {(onApprove || onReject) && (
                  <td className="px-4 py-4 text-sm">
                    {pending ? (
                      <div className="flex gap-2">
                        {onApprove && <button type="button" disabled={isUpdating} onClick={() => onApprove(decision.id)} className="rounded bg-green-600 px-2 py-1 text-xs font-semibold text-white hover:bg-green-700 disabled:bg-gray-400">Approve Paper</button>}
                        {onReject && <button type="button" disabled={isUpdating} onClick={() => onReject(decision.id)} className="rounded border border-red-300 px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:text-gray-400">Reject</button>}
                      </div>
                    ) : <span className="text-xs text-gray-500">—</span>}
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
