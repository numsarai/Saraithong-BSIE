import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import { Step3Config } from '@/components/steps/Step3Config'
import { useStore } from '@/store'

vi.mock('@/api', () => ({
  getBanks: vi.fn(async () => ([
    { key: 'scb', name: 'SCB' },
    { key: 'ktb', name: 'KTB' },
  ])),
  lookupRememberedAccountName: vi.fn(async () => ({ matched: false, remembered_name: '' })),
  startProcess: vi.fn(async () => ({ job_id: 'job-1', parser_run_id: 'run-1' })),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const { lookupRememberedAccountName } = await import('@/api')

describe('Step3Config remembered account name', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useStore.getState().reset()
    useStore.setState({
      step: 3,
      tempFilePath: '/tmp/example.xlsx',
      bankKey: 'scb',
      account: '1234567890',
      name: '',
      confirmedMapping: {},
      headerRow: 1,
      sheetName: 'Sheet1',
    })
  })

  it('prefills a blank subject name from remembered account memory', async () => {
    vi.mocked(lookupRememberedAccountName).mockResolvedValueOnce({
      matched: true,
      account: '1234567890',
      normalized_account_number: '1234567890',
      bank_key: 'scb',
      remembered_name: 'Persisted Name',
    })

    render(<Step3Config />)

    expect(await screen.findByDisplayValue('Persisted Name')).toBeInTheDocument()
    expect(screen.getByText(/remembered from previous imports/i)).toBeInTheDocument()
  })

  it('shows the remembered name without overwriting a manual name', async () => {
    useStore.setState({ name: 'Manual Name' })
    vi.mocked(lookupRememberedAccountName).mockResolvedValueOnce({
      matched: true,
      account: '1234567890',
      normalized_account_number: '1234567890',
      bank_key: 'scb',
      remembered_name: 'Persisted Name',
    })

    render(<Step3Config />)

    await waitFor(() => expect(screen.getByText(/remembered from previous imports/i)).toBeInTheDocument())
    expect(screen.getByDisplayValue('Manual Name')).toBeInTheDocument()
  })
})
