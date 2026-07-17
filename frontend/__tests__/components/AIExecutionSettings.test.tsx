import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import AIExecutionSettings from '@/components/AIExecutionSettings'
import API from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    patch: jest.fn(),
  },
}))

const mockedApi = API as jest.Mocked<typeof API>

describe('AIExecutionSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockedApi.get.mockImplementation(async (path: string) => {
      if (path === '/ai/settings') {
        return { data: { execution_mode: 'manual_approval', model_key: 'rule_based_v1', paper_only: true } }
      }
      return { data: { models: [{ key: 'rule_based_v1', display_name: 'Rule-based paper model', version: '1.0' }] } }
    })
    mockedApi.patch.mockResolvedValue({
      data: { execution_mode: 'automatic_paper', model_key: 'rule_based_v1', paper_only: true },
    })
  })

  it('keeps manual approval as the default and only exposes automatic paper execution', async () => {
    render(<AIExecutionSettings />)

    expect(await screen.findByText('Live Locked')).toBeInTheDocument()
    expect(screen.getByText(/never connects to a real broker/i)).toBeInTheDocument()
    await screen.findByLabelText('Execution policy')
    expect(screen.getByRole('option', { name: 'Manual approval (default)' })).toBeInTheDocument()
    expect(screen.queryByText(/live execution/i)).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Execution policy'), { target: { value: 'automatic_paper' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save AI Settings' }))

    await waitFor(() => expect(mockedApi.patch).toHaveBeenCalledWith('/ai/settings', {
      execution_mode: 'automatic_paper',
      model_key: 'rule_based_v1',
    }))
    expect(await screen.findByText(/automatic paper execution is enabled/i)).toBeInTheDocument()
  })
})
