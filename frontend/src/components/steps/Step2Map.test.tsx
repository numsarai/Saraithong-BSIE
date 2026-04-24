import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Step2Map } from '@/components/steps/Step2Map'
import { useStore } from '@/store'
import { toast } from 'sonner'

vi.mock('@/api', () => ({
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
  getBanks: vi.fn(async () => ([
    { key: 'scb', name: 'SCB', logo_url: '/api/bank-logos/scb.svg' },
    { key: 'ktb', name: 'KTB', logo_url: '/api/bank-logos/ktb.svg' },
    { key: 'ciaf', name: 'CIAF Export', logo_url: '/api/bank-logos/ciaf.svg' },
  ])),
  learnBank: vi.fn(async () => ({ status: 'ok' })),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const { confirmMapping, previewMapping } = await import('@/api')

function seedUpload(data: Record<string, unknown> = {}) {
  useStore.getState().setUploadResult({
    temp_file_path: '/tmp/example.xlsx',
    detected_bank: {
      key: 'scb',
      bank: 'SCB',
      confidence: 0.91,
      ambiguous: false,
      scores: { scb: 10.2, ktb: 4.1 },
      top_candidates: ['scb', 'ktb'],
      evidence: { positive: [], negative: [], layout: 'dual_account_like' },
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
    ...data,
  }, 'example.xlsx')
}

describe('Step2Map analyst gate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useStore.getState().reset()
    useStore.setState({ operatorName: 'Case Reviewer' })
  })

  it('blocks ambiguous detections until the bank is explicitly confirmed', async () => {
    seedUpload({
      detected_bank: {
        key: 'scb',
        bank: 'SCB',
        confidence: 0.92,
        ambiguous: true,
        scores: { scb: 10.2, ktb: 9.8 },
        top_candidates: ['scb', 'ktb'],
        evidence: { positive: ['keyword:SCB'], negative: [], layout: 'dual_account_like' },
      },
    })

    render(<Step2Map />)

    const continueButton = await screen.findByRole('button', { name: /^confirm mapping$/i })
    expect(continueButton).toBeDisabled()
    expect(screen.getByText(/analyst review required before step 3/i)).toBeInTheDocument()
    expect(screen.getAllByAltText('SCB logo').length).toBeGreaterThan(0)
    expect(screen.getAllByAltText('KTB logo').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: /confirm selected bank/i }))

    await waitFor(() => expect(continueButton).toBeEnabled())
    fireEvent.click(continueButton)

    await waitFor(() => expect(confirmMapping).toHaveBeenCalledTimes(1))
    expect(previewMapping).toHaveBeenCalledTimes(1)
    expect(useStore.getState().step).toBe(3)
  })

  it('requires mapping readiness when critical mapping is incomplete', async () => {
    seedUpload({
      suggested_mapping: {
        date: 'วันที่',
        description: null,
        amount: null,
        debit: null,
        credit: null,
      },
      confidence_scores: { date: 100, description: 0, amount: 0, debit: 0, credit: 0 },
    })

    render(<Step2Map />)

    const continueButton = await screen.findByRole('button', { name: /^confirm mapping$/i })
    const mappingConfirmButton = screen.getByRole('button', { name: /confirm mapping readiness/i })
    const selects = screen.getAllByRole('combobox')

    expect(continueButton).toBeDisabled()
    expect(mappingConfirmButton).toBeDisabled()

    fireEvent.change(selects[3], { target: { value: 'รายละเอียด' } })
    fireEvent.change(selects[4], { target: { value: 'จำนวนเงิน' } })

    await waitFor(() => expect(screen.getByRole('button', { name: /confirm mapping readiness/i })).toBeEnabled())

    fireEvent.click(screen.getByRole('button', { name: /confirm mapping readiness/i }))

    await waitFor(() => expect(continueButton).toBeEnabled())
  })

  it('clears bank review when the selected bank changes', async () => {
    seedUpload({
      detected_bank: {
        key: 'scb',
        bank: 'SCB',
        confidence: 0.6,
        ambiguous: false,
        scores: { scb: 7.0, ktb: 6.0 },
        top_candidates: ['scb', 'ktb'],
        evidence: { positive: [], negative: ['low_confidence'], layout: 'unknown' },
      },
    })

    render(<Step2Map />)

    const continueButton = await screen.findByRole('button', { name: /^confirm mapping$/i })
    fireEvent.click(screen.getByRole('button', { name: /confirm selected bank/i }))

    await waitFor(() => expect(continueButton).toBeEnabled())

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'ktb' } })

    await waitFor(() => expect(continueButton).toBeDisabled())
    expect(screen.getAllByText('Required').length).toBeGreaterThan(0)
  })

  it('clears mapping review when a critical mapping changes after confirmation', async () => {
    seedUpload({
      detected_bank: {
        key: 'scb',
        bank: 'SCB',
        confidence: 0.94,
        ambiguous: false,
        scores: { scb: 12.0 },
        top_candidates: ['scb'],
        evidence: { positive: [], negative: [], layout: 'dual_account_like' },
      },
      suggested_mapping: {
        date: 'วันที่',
        description: 'รายละเอียด',
        amount: null,
        debit: 'ถอนเงิน',
        credit: null,
      },
      confidence_scores: { date: 100, description: 100, debit: 100 },
    })

    render(<Step2Map />)

    const continueButton = await screen.findByRole('button', { name: /^confirm mapping$/i })
    expect(continueButton).toBeEnabled()
    expect(screen.getByRole('button', { name: /mapping confirmed/i })).toBeInTheDocument()

    const selects = screen.getAllByRole('combobox')
    fireEvent.change(selects[5], { target: { value: '' } })

    await waitFor(() => expect(continueButton).toBeDisabled())
  })

  it('passes detected context when confirming and surfaces correction feedback', async () => {
    vi.mocked(confirmMapping).mockResolvedValueOnce({
      status: 'ok',
      feedback_mode: 'corrected',
      message: 'Saved and reinforced your correction',
    })

    seedUpload()
    render(<Step2Map />)

    fireEvent.click(await screen.findByRole('button', { name: /^confirm mapping$/i }))

    await waitFor(() => expect(confirmMapping).toHaveBeenCalledTimes(1))
    expect(previewMapping).toHaveBeenCalledWith({
      bank: 'scb',
      mapping: {
        date: 'วันที่',
        description: 'รายละเอียด',
        amount: 'จำนวนเงิน',
      },
      columns: ['วันที่', 'รายละเอียด', 'จำนวนเงิน', 'ถอนเงิน', 'ฝากเงิน'],
      sample_rows: [{ วันที่: '2026-01-01', รายละเอียด: 'โอนเงิน', จำนวนเงิน: '100.00' }],
    })
    expect(confirmMapping).toHaveBeenCalledWith(
      'scb',
      {
        date: 'วันที่',
        description: 'รายละเอียด',
        amount: 'จำนวนเงิน',
      },
      ['วันที่', 'รายละเอียด', 'จำนวนเงิน', 'ถอนเงิน', 'ฝากเงิน'],
      1,
      'Sheet1',
      {
        reviewer: 'Case Reviewer',
        detected_bank: expect.objectContaining({ key: 'scb' }),
        suggested_mapping: {
          date: 'วันที่',
            description: 'รายละเอียด',
          amount: 'จำนวนเงิน',
        },
        sample_rows: [{ วันที่: '2026-01-01', รายละเอียด: 'โอนเงิน', จำนวนเงิน: '100.00' }],
        promote_shared: false,
      },
    )
    expect(toast.success).toHaveBeenCalledWith('Saved and reinforced your correction')
  })
})
