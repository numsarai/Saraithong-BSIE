import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '@/App'
import { useStore } from '@/store'

vi.mock('@/api', () => ({
  uploadFile: vi.fn(),
  confirmMapping: vi.fn(async () => ({ status: 'ok' })),
  getBanks: vi.fn(async () => ([
    { key: 'scb', name: 'SCB' },
    { key: 'ktb', name: 'KTB' },
  ])),
  learnBank: vi.fn(async () => ({ status: 'ok' })),
  startProcess: vi.fn(async () => ({ job_id: 'job-1' })),
  getJobStatus: vi.fn(async () => ({ status: 'queued', log: [] })),
  getResults: vi.fn(async () => ({ items: [], total: 0 })),
  processFolder: vi.fn(async () => ({ total_files: 0, processed_files: 0, skipped_files: 0, error_files: 0, files: [], accounts: [] })),
  getBank: vi.fn(async () => ({ key: 'scb', bank_name: 'SCB' })),
  createBank: vi.fn(async () => ({ status: 'ok' })),
  deleteBank: vi.fn(async () => ({ status: 'ok' })),
  learnBankDetection: vi.fn(async () => ({ status: 'ok' })),
  saveOverride: vi.fn(async () => ({ status: 'ok' })),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
  Toaster: () => null,
}))

const { uploadFile, confirmMapping, getBanks } = await import('@/api')
let consoleErrorSpy: ReturnType<typeof vi.spyOn> | null = null
const originalConsoleError = console.error

async function flushAsyncWork() {
  await Promise.resolve()
  await Promise.resolve()
}

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  )
}

function makeUploadResponse(overrides: Record<string, unknown> = {}) {
  return {
    temp_file_path: '/tmp/sample.xlsx',
    detected_bank: {
      key: 'scb',
      bank: 'SCB',
      confidence: 0.9,
      ambiguous: false,
      scores: { scb: 10.1, ktb: 4.5 },
      top_candidates: ['scb', 'ktb'],
      evidence: { positive: ['keyword:SCB'], negative: [], layout: 'dual_account_like' },
    },
    suggested_mapping: {
      date: 'วันที่',
      description: 'รายละเอียด',
      amount: 'จำนวนเงิน',
    },
    all_columns: ['วันที่', 'รายละเอียด', 'จำนวนเงิน', 'ถอนเงิน', 'ฝากเงิน'],
    confidence_scores: { date: 100, description: 100, amount: 100 },
    sample_rows: [{ วันที่: '2026-01-01', รายละเอียด: 'โอนเงิน', จำนวนเงิน: '100.00' }],
    header_row: 1,
    sheet_name: 'Sheet1',
    memory_match: null,
    bank_memory_match: null,
    ...overrides,
  }
}

async function uploadSample(container: HTMLElement, filename = 'sample.xlsx') {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement | null
  expect(input).not.toBeNull()
  const file = new File(['bank data'], filename, {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  await act(async () => {
    fireEvent.change(input!, { target: { files: [file] } })
  })
  await screen.findByText(/detect & map columns/i)
}

describe('App workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useStore.getState().reset()
    vi.mocked(getBanks).mockImplementation(() => new Promise(() => {}))
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation((message?: unknown, ...args: unknown[]) => {
      if (typeof message === 'string' && message.includes('not wrapped in act')) {
        return
      }
      originalConsoleError(message, ...args)
    })
  })

  afterEach(() => {
    useStore.getState().reset()
    consoleErrorSpy?.mockRestore()
    consoleErrorSpy = null
  })

  it('forces analyst review in the full upload flow for ambiguous bank detection', async () => {
    vi.mocked(uploadFile).mockResolvedValueOnce(makeUploadResponse({
      detected_bank: {
        key: 'scb',
        bank: 'SCB',
        confidence: 0.88,
        ambiguous: true,
        scores: { scb: 10.0, ktb: 9.7 },
        top_candidates: ['scb', 'ktb'],
        evidence: { positive: ['keyword:SCB'], negative: ['margin_low'], layout: 'dual_account_like' },
      },
    }))

    const { container } = renderApp()
    await uploadSample(container, 'ambiguous.xlsx')

    const continueButton = await screen.findByRole('button', { name: /continue to configure/i })
    expect(continueButton).toBeDisabled()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /confirm selected bank/i }))
      await flushAsyncWork()
    })

    await waitFor(() => expect(continueButton).toBeEnabled())

    await act(async () => {
      fireEvent.click(continueButton)
      await flushAsyncWork()
      await screen.findByText(/configure pipeline/i)
    })

    await waitFor(() => expect(confirmMapping).toHaveBeenCalledTimes(1))
    expect(screen.getByText(/configure pipeline/i)).toBeInTheDocument()
  })

  it('allows fast progression for strong auto-detected uploads', async () => {
    vi.mocked(uploadFile).mockResolvedValueOnce(makeUploadResponse())

    const { container } = renderApp()
    await uploadSample(container, 'strong.xlsx')

    const continueButton = await screen.findByRole('button', { name: /continue to configure/i })
    expect(continueButton).toBeEnabled()

    await act(async () => {
      fireEvent.click(continueButton)
      await flushAsyncWork()
      await screen.findByText(/configure pipeline/i)
    })

    await waitFor(() => expect(confirmMapping).toHaveBeenCalledTimes(1))
    expect(screen.getByText(/configure pipeline/i)).toBeInTheDocument()
  })
})
