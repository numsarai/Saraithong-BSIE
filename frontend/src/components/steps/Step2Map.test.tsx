import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Step2Map } from '@/components/steps/Step2Map'
import { useStore } from '@/store'
import { toast } from 'sonner'

vi.mock('@/api', () => ({
  assistMapping: vi.fn(async () => ({
    status: 'ok',
    source: 'local_llm_mapping_assist',
    suggestion_only: true,
    auto_pass_eligible: false,
    model: 'qwen2.5:14b',
    mapping: {
      date: 'วันที่',
      description: 'รายละเอียด',
      debit: 'ถอนเงิน',
      credit: 'ฝากเงิน',
      balance: null,
    },
    confidence: 0.84,
    reasons: ['Debit and credit headers are explicit'],
    warnings: [],
    validation: { ok: true, errors: [], warnings: [], amount_mode: 'debit_credit', mapped_fields: ['date', 'description', 'debit', 'credit'] },
  })),
  assistVisionMapping: vi.fn(async () => ({
    status: 'ok',
    source: 'local_llm_vision_mapping_assist',
    suggestion_only: true,
    auto_pass_eligible: false,
    model: 'qwen2.5vl:7b',
    mapping: {
      date: 'วันที่',
      description: 'รายละเอียด',
      debit: 'ถอนเงิน',
      credit: 'ฝากเงิน',
      balance: null,
    },
    confidence: 0.79,
    reasons: ['Visual table labels match OCR columns'],
    warnings: [],
    file_context: { source_type: 'pdf_vision', page_count: 1, preview_page: 1 },
    validation: { ok: true, errors: [], warnings: [], amount_mode: 'debit_credit', mapped_fields: ['date', 'description', 'debit', 'credit'] },
  })),
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

const { assistMapping, assistVisionMapping, confirmMapping, previewMapping } = await import('@/api')

function seedUpload(data: Record<string, unknown> = {}, filename = 'example.xlsx') {
  useStore.getState().setUploadResult({
    temp_file_path: '/tmp/example.xlsx',
    file_id: 'file-1',
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
  }, filename)
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

  it('shows guarded template variant suggestions as analyst-visible memory', async () => {
    seedUpload({
      suggestion_source: 'template_variant',
      template_variant_match: {
        variant_id: 'VARIANT-TRUSTED',
        bank_key: 'scb',
        trust_state: 'trusted',
        match_type: 'ordered_signature',
        match_score: 1,
        confirmation_count: 3,
        correction_count: 0,
        reviewer_count: 2,
        suggestion_only: true,
        auto_pass_eligible: false,
      },
    })

    render(<Step2Map />)

    expect(await screen.findByText(/template variant matched/i)).toBeInTheDocument()
    expect(screen.getByText(/scb trusted via ordered signature/i)).toBeInTheDocument()
  })

  it('applies local LLM mapping assist only after analyst action', async () => {
    seedUpload({
      suggested_mapping: {
        date: 'วันที่',
        description: 'รายละเอียด',
        amount: null,
        debit: null,
        credit: null,
      },
    })

    render(<Step2Map />)

    fireEvent.click(await screen.findByRole('button', { name: /ask assist/i }))

    expect(await screen.findByText(/debit and credit headers are explicit/i)).toBeInTheDocument()
    expect(assistMapping).toHaveBeenCalledWith({
      bank: 'scb',
      detected_bank: expect.objectContaining({ key: 'scb' }),
      columns: ['วันที่', 'รายละเอียด', 'จำนวนเงิน', 'ถอนเงิน', 'ฝากเงิน'],
      sample_rows: [{ วันที่: '2026-01-01', รายละเอียด: 'โอนเงิน', จำนวนเงิน: '100.00' }],
      current_mapping: {
        date: 'วันที่',
        description: 'รายละเอียด',
        amount: null,
        debit: null,
        credit: null,
      },
      subject_account: '',
      subject_name: '',
      identity_guess: null,
      sheet_name: 'Sheet1',
      header_row: 1,
    })
    expect(useStore.getState().confirmedMapping.credit).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /apply suggestion/i }))

    await waitFor(() => expect(useStore.getState().confirmedMapping.credit).toBe('ฝากเงิน'))
    expect(useStore.getState().confirmedMapping.debit).toBe('ถอนเงิน')
  })

  it('uses local vision mapping assist for PDF/image uploads only after analyst action', async () => {
    seedUpload({
      suggested_mapping: {
        date: 'วันที่',
        description: 'รายละเอียด',
        amount: null,
        debit: null,
        credit: null,
      },
      sheet_name: 'PDF_OCR',
    }, 'scan.pdf')

    render(<Step2Map />)

    fireEvent.click(await screen.findByRole('button', { name: /ask vision/i }))

    expect(await screen.findByText(/visual table labels match ocr columns/i)).toBeInTheDocument()
    expect(assistVisionMapping).toHaveBeenCalledWith({
      file_id: 'file-1',
      bank: 'scb',
      detected_bank: expect.objectContaining({ key: 'scb' }),
      columns: ['วันที่', 'รายละเอียด', 'จำนวนเงิน', 'ถอนเงิน', 'ฝากเงิน'],
      sample_rows: [{ วันที่: '2026-01-01', รายละเอียด: 'โอนเงิน', จำนวนเงิน: '100.00' }],
      current_mapping: {
        date: 'วันที่',
        description: 'รายละเอียด',
        amount: null,
        debit: null,
        credit: null,
      },
      subject_account: '',
      subject_name: '',
      identity_guess: null,
      sheet_name: 'PDF_OCR',
      header_row: 1,
    })
    expect(useStore.getState().confirmedMapping.credit).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /apply suggestion/i }))

    await waitFor(() => expect(useStore.getState().confirmedMapping.credit).toBe('ฝากเงิน'))
    expect(useStore.getState().confirmedMapping.debit).toBe('ถอนเงิน')
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

  it('blocks high-confidence bank overrides until explicitly confirmed', async () => {
    seedUpload({
      detected_bank: {
        key: 'scb',
        bank: 'SCB',
        confidence: 0.96,
        ambiguous: false,
        scores: { scb: 12.0, ktb: 4.0 },
        top_candidates: ['scb', 'ktb'],
        evidence: { positive: ['keyword:SCB'], negative: [], layout: 'dual_account_like' },
      },
    })

    render(<Step2Map />)

    const continueButton = await screen.findByRole('button', { name: /^confirm mapping$/i })
    expect(continueButton).toBeEnabled()

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'ktb' } })

    await waitFor(() => expect(continueButton).toBeDisabled())
    expect(screen.getByText(/selected bank overrides auto-detection/i)).toBeInTheDocument()
    expect(screen.getByText(/selected bank \(KTB\) differs from detected bank \(SCB\)/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /confirm selected bank/i }))

    await waitFor(() => expect(continueButton).toBeEnabled())
    fireEvent.click(continueButton)

    await waitFor(() => expect(confirmMapping).toHaveBeenCalledTimes(1))
    expect(previewMapping).toHaveBeenCalledWith(expect.objectContaining({ bank: 'ktb' }))
    expect(confirmMapping).toHaveBeenCalledWith(
      'ktb',
      expect.any(Object),
      expect.any(Array),
      1,
      'Sheet1',
      expect.objectContaining({
        detected_bank: expect.objectContaining({ key: 'scb' }),
      }),
    )
  })

  it('blocks inferred account overrides until explicitly confirmed', async () => {
    seedUpload({
      account_guess: '1111111111',
      name_guess: 'Detected Name',
      identity_guess: {
        account: '1111111111',
        name: 'Detected Name',
        account_source: 'workbook_header',
        name_source: 'workbook_header',
      },
    })

    render(<Step2Map />)

    const continueButton = await screen.findByRole('button', { name: /^confirm mapping$/i })
    expect(continueButton).toBeEnabled()

    fireEvent.change(screen.getByLabelText(/known account number/i), { target: { value: '2222222222' } })

    await waitFor(() => expect(continueButton).toBeDisabled())
    expect(screen.getByText(/selected account \(2222222222\) differs from inferred account \(1111111111\)/i)).toBeInTheDocument()
    expect(screen.getByText(/BSIE inferred/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /confirm known account/i }))

    await waitFor(() => expect(continueButton).toBeEnabled())
    fireEvent.click(continueButton)

    await waitFor(() => expect(confirmMapping).toHaveBeenCalledTimes(1))
    expect(confirmMapping).toHaveBeenCalledWith(
      'scb',
      expect.any(Object),
      expect.any(Array),
      1,
      'Sheet1',
      expect.objectContaining({
        subject_account: '2222222222',
        subject_name: 'Detected Name',
        identity_guess: expect.objectContaining({ account: '1111111111' }),
      }),
    )
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
    fireEvent.change(selects[6], { target: { value: '' } })

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
        subject_account: '',
        subject_name: '',
        identity_guess: null,
        sample_rows: [{ วันที่: '2026-01-01', รายละเอียด: 'โอนเงิน', จำนวนเงิน: '100.00' }],
        promote_shared: false,
      },
    )
    expect(toast.success).toHaveBeenCalledWith('Saved and reinforced your correction')
  })
})
