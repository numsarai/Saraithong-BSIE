import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '@/App'
import { useStore } from '@/store'

vi.mock('@/api', () => ({
  uploadFile: vi.fn(),
  assistMapping: vi.fn(async () => ({ status: 'ok' })),
  assistVisionMapping: vi.fn(async () => ({ status: 'ok' })),
  confirmMapping: vi.fn(async () => ({ status: 'ok' })),
  previewMapping: vi.fn(async () => ({
    status: 'ok',
    ok: true,
    errors: [],
    warnings: [],
    dry_run_preview: {
      summary: { valid_transaction_rows: 1, preview_row_count: 1 },
      rows: [{ row_index: 1, date: '2026-01-01', amount: 100, direction: 'IN', status: 'ok' }],
    },
  })),
  verifyAccountPresence: vi.fn(async () => ({ status: 'ok', found: true, match_status: 'exact_found', summary: {} })),
  getBanks: vi.fn(async () => ([
    { key: 'scb', name: 'SCB' },
    { key: 'ktb', name: 'KTB' },
  ])),
  lookupRememberedAccountName: vi.fn(async () => ({ matched: false, remembered_name: '' })),
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
  llmChat: vi.fn(async () => ({ response: 'ok' })),
  getLlmStatus: vi.fn(async () => ({ status: 'ok', models: [] })),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
  Toaster: () => null,
}))

vi.mock('@/components/LlmChat', () => ({
  LlmChat: () => null,
}))

const { uploadFile, confirmMapping, getBanks, previewMapping } = await import('@/api')

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
    act(() => {
      useStore.getState().reset()
      useStore.setState({ operatorName: 'Case Reviewer' })
    })
    vi.mocked(getBanks).mockImplementation(() => new Promise(() => {}))
  })

  afterEach(() => {
    act(() => {
      useStore.getState().reset()
    })
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
    expect(uploadFile).toHaveBeenCalledWith(expect.any(File), 'Case Reviewer')

    const continueButton = await screen.findByRole('button', { name: /^confirm mapping$/i })
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
    expect(previewMapping).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/configure pipeline/i)).toBeInTheDocument()
  })

  it('allows fast progression for strong auto-detected uploads', async () => {
    vi.mocked(uploadFile).mockResolvedValueOnce(makeUploadResponse())

    const { container } = renderApp()
    await uploadSample(container, 'strong.xlsx')
    expect(uploadFile).toHaveBeenCalledWith(expect.any(File), 'Case Reviewer')

    const continueButton = await screen.findByRole('button', { name: /^confirm mapping$/i })
    expect(continueButton).toBeEnabled()

    await act(async () => {
      fireEvent.click(continueButton)
      await flushAsyncWork()
      await screen.findByText(/configure pipeline/i)
    })

    await waitFor(() => expect(confirmMapping).toHaveBeenCalledTimes(1))
    expect(previewMapping).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/configure pipeline/i)).toBeInTheDocument()
  })
})
