import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import BrokerSettingsPage from '@/app/dashboard/broker-settings/page'
import API from '@/lib/api'

jest.mock('@/components/Layout', () => {
  return ({ children }: { children: React.ReactNode }) => <div>{children}</div>
})

jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
  getSessionValue: jest.fn(() => null),
}))

const mockedApi = API as jest.Mocked<typeof API>

describe('BrokerSettingsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    localStorage.clear()
    mockedApi.get.mockResolvedValue({ data: { configurations: [] } })
  })

  it('shows disconnected, paper-ready, and locked-live safeguards', async () => {
    render(<BrokerSettingsPage />)

    await waitFor(() => expect(mockedApi.get).toHaveBeenCalledWith('/broker-configurations'))
    expect(await screen.findByText('Not Tested')).toBeInTheDocument()
    expect(screen.getByText('Disconnected')).toBeInTheDocument()
    expect(screen.getByText('Live Locked')).toBeInTheDocument()
    expect(screen.getByText('Paper Ready')).toBeInTheDocument()
    expect(screen.getByText(/never asks for passwords, API keys, or account numbers/i)).toBeInTheDocument()
  })

  it('saves a paper profile and runs only the mock connection test', async () => {
    const configuration = {
      id: 'paper-1',
      name: 'Saved Paper Profile',
      broker: 'interactive_brokers',
      mode: 'paper',
      host: '127.0.0.1',
      port: 7497,
      client_id: 1,
      profile_label: '',
      status: 'disconnected',
      last_mock_tested_at: null,
    }
    let configurations: Array<typeof configuration> = []
    mockedApi.get.mockImplementation(async () => ({ data: { configurations } }))
    mockedApi.post.mockImplementation(async (url: string) => {
      if (url === '/broker-configurations') {
        configurations = [configuration]
        return { data: configuration }
      }
      configurations = [{ ...configuration, status: 'paper_ready' }]
      return {
        data: {
          test_mode: 'mock',
          status: 'paper_ready',
          message: 'Mock test passed. Paper configuration is ready; IBKR remains disconnected.',
        },
      }
    })

    render(<BrokerSettingsPage />)

    await screen.findByText('No broker configurations saved yet.')
    fireEvent.change(screen.getByLabelText('Configuration Name'), {
      target: { value: configuration.name },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add Configuration' }))

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith(
      '/broker-configurations',
      expect.objectContaining({ mode: 'paper', broker: 'interactive_brokers' }),
    ))
    expect(await screen.findByText(configuration.name)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Run Mock Test' }))

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith(
      `/broker-configurations/${configuration.id}/test`,
    ))
    expect(await screen.findByText(/mock test passed.*ibkr remains disconnected/i)).toBeInTheDocument()
    expect(await screen.findByText('Ready')).toBeInTheDocument()
  })
})
