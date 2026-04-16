import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { act } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('@/components/AccountFlowGraph', () => ({
  AccountFlowGraph: ({ rows }: { rows: Array<{ transaction_datetime?: string }> }) => (
    <div
      data-testid="account-flow-graph"
      data-count={String(rows.length)}
      data-first-datetime={String(rows[0]?.transaction_datetime || '')}
    />
  ),
}))

vi.mock('@/components/TimelineChart', () => ({
  TimelineChart: ({ transactions }: { transactions: Array<{ transaction_datetime?: string }> }) => (
    <div
      data-testid="timeline-chart"
      data-count={String(transactions.length)}
      data-first-datetime={String(transactions[0]?.transaction_datetime || '')}
    />
  ),
}))

vi.mock('@/components/TimeWheel', () => ({
  TimeWheel: ({ transactions }: { transactions: Array<{ transaction_datetime?: string }> }) => (
    <div
      data-testid="time-wheel"
      data-count={String(transactions.length)}
      data-first-datetime={String(transactions[0]?.transaction_datetime || '')}
    />
  ),
}))

import { Step5Results } from '@/components/steps/Step5Results'
import { useStore } from '@/store'

vi.mock('@/api', () => ({
  getResults: vi.fn(async () => ({
    rows: [
      {
        transaction_id: 'TXN-001',
        date: '2026-03-30T23:30:00Z',
        amount: 1000,
        direction: 'IN',
        transaction_type: 'transfer_in',
        confidence: 0.9,
        counterparty_account: '2222222222',
        counterparty_name: 'Alice',
        description: 'Transfer',
        from_account: '2222222222',
        to_account: '1234567890',
        is_overridden: false,
      },
    ],
    total: 1,
    meta: {
      bank: 'SCB',
      num_transactions: 1,
      total_in: 1000,
      total_out: 0,
      total_circulation: 1000,
      date_range: '2026-03-01 to 2026-03-10',
      category_counts: {},
      reconciliation: {
        status: 'FAILED',
        matched_rows: 1,
        mismatched_rows: 3,
        missing_balance_rows: 0,
        max_abs_difference: 400,
        chronology_issue_detected: true,
        chronological_mismatched_rows: 1,
        chronological_status: 'PARTIAL',
        chronological_max_abs_difference: 0.32,
        mismatches_reduced_by_sorting: 2,
        rounding_drift_rows: 1,
        material_mismatched_rows: 0,
        missing_time_rows: 0,
        duplicate_timestamp_rows: 0,
        recommended_check_mode: 'chronological',
        guidance_th: [
          'รายการใน statement น่าจะไม่เรียงตามเวลา ควรดูผลแบบเรียงตามเวลา',
          'มีแถวที่ต่างกันเพียงเศษสตางค์หรือส่วนต่างเล็กน้อย',
        ],
        check_modes: {
          file_order: { label: 'File Order', status: 'FAILED', mismatched_rows: 3, max_abs_difference: 400 },
          chronological: { label: 'Chronological', status: 'PARTIAL', mismatched_rows: 1, max_abs_difference: 0.32 },
        },
      },
    },
    entities: [
      {
        entity_id: 'ENT-001',
        entity_type: 'Person',
        value: 'Alice',
        count: 1,
        first_seen: '2026-03-01',
        last_seen: '2026-03-10T18:00:00Z',
      },
    ],
    links: [
      {
        transaction_id: 'TXN-001',
        from_account: '2222222222',
        to_account: '1234567890',
        amount: 1000,
        date: '2026-03-05',
        transaction_type: 'transfer_in',
      },
    ],
  })),
  getResultsTimeline: vi.fn(async () => ({
    items: [
      {
        date: '2026-03-01',
        posted_date: '2026-03-01',
        transaction_datetime: '2026-03-01T08:15:00Z',
        amount: 1000,
        direction: 'IN',
        transaction_type: 'transfer_in',
        counterparty_account: '2222222222',
        counterparty_name: 'Alice',
      },
      {
        date: '2026-03-02',
        posted_date: '2026-03-02',
        transaction_datetime: '2026-03-02T19:45:00Z',
        amount: 350,
        direction: 'OUT',
        transaction_type: 'transfer_out',
        counterparty_account: '3333333333',
        counterparty_name: 'Bob',
      },
    ],
    total: 2,
  })),
  getAccountInsights: vi.fn(async () => ({ insights: [] })),
  generateAccountReport: vi.fn(async () => undefined),
  getOverrides: vi.fn(async () => ({
    overrides: [
      {
        account_number: '1234567890',
        transaction_id: 'TXN-001',
        override_from_account: '2222222222',
        override_to_account: '1234567890',
        override_reason: 'confirmed',
        override_by: 'analyst',
        override_timestamp: '2026-03-30T23:30:00Z',
      },
    ],
  })),
  saveOverride: vi.fn(async () => ({ status: 'ok' })),
  deleteOverride: vi.fn(async () => ({ status: 'ok' })),
}))

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}))

const { deleteOverride, getResults, getResultsTimeline } = await import('@/api')

function renderWithQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <Step5Results />
    </QueryClientProvider>
  )
}

describe('Step5Results date formatting', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useStore.getState().reset()
    useStore.setState({
      account: '1234567890',
      bankKey: 'scb',
      parserRunId: 'RUN-STEP5',
      operatorName: 'Case Reviewer',
      currentTab: 'transactions',
      results: null,
    })
  })

  it('renders table dates as DD MM YYYY and supports balance check mode switching', async () => {
    renderWithQueryClient()

    expect(await screen.findByAltText('SCB logo')).toBeInTheDocument()
    expect(await screen.findByText('31 03 2026')).toBeInTheDocument()
    expect(screen.getByText('01 03 2026 to 10 03 2026')).toBeInTheDocument()
    expect(screen.getByText('คำแนะนำสำหรับผู้ใช้งาน')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Chronological' })).toBeInTheDocument()
    expect(screen.getAllByText('PARTIAL').length).toBeGreaterThan(0)

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'File Order' }))
    })
    expect(screen.getAllByText('FAILED').length).toBeGreaterThan(0)

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Entities' }))
    })
    expect(await screen.findByText('01 03 2026')).toBeInTheDocument()
    expect(screen.getByText('11 03 2026')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Links' }))
    })
    expect(await screen.findByText('05 03 2026')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Transactions' }))
    })
    expect(screen.getByText(/analyst · 31 03 2026/i)).toBeInTheDocument()
  })

  it('passes the stored operator when deleting an override', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: /delete/i }))

    await act(async () => {
      await Promise.resolve()
    })

    expect(deleteOverride).toHaveBeenCalledWith('TXN-001', '1234567890', 'Case Reviewer')
    confirmSpy.mockRestore()
  })

  it('uses meta transaction count in the header before paged results total is ready', async () => {
    useStore.setState({
      account: '1883167399',
      bankKey: 'kbank',
      results: {
        meta: {
          bank: 'KBANK',
          num_transactions: 1595,
          total_in: 2316072.58,
          total_out: -2316071.95,
          total_circulation: 4632144.53,
          date_range: '2024-07-07 to 2025-07-20',
          category_counts: {},
          reconciliation: {},
        },
      },
    })

    renderWithQueryClient()

    expect(await screen.findByText(/1883167399 · KBANK · 1595 transactions/i)).toBeInTheDocument()
  })

  it('renders preview rows from job results before paged query data returns', async () => {
    vi.mocked(getResults).mockImplementationOnce(() => new Promise(() => {}))
    useStore.setState({
      account: '1883167399',
      bankKey: 'kbank',
      results: {
        meta: {
          bank: 'KBANK',
          num_transactions: 1595,
          total_in: 2316072.58,
          total_out: -2316071.95,
          total_circulation: 4632144.53,
          date_range: '2024-07-07 to 2025-07-20',
          category_counts: {},
          reconciliation: {},
        },
        transactions: [
          {
            transaction_id: 'KBANK-PREVIEW-1',
            date: '2025-07-20',
            amount: '2500.00',
            direction: 'IN',
            transaction_type: 'transfer_in',
            confidence: '0.98',
            counterparty_account: '9999999999',
            counterparty_name: 'Preview Sender',
            description: 'Preview transfer',
            from_account: '9999999999',
            to_account: '1883167399',
            is_overridden: false,
          },
        ],
      },
    })

    renderWithQueryClient()

    expect(await screen.findByText('KBANK-PREVIEW-1')).toBeInTheDocument()
    expect(screen.getByText(/1883167399 · KBANK · 1595 transactions/i)).toBeInTheDocument()
    expect(screen.getByText(/Showing preview rows while the full results query finishes loading/i)).toBeInTheDocument()
  })

  it('requests full results for the active parser run', async () => {
    renderWithQueryClient()

    await screen.findByText('31 03 2026')

    expect(getResults).toHaveBeenCalledWith('1234567890', 1, 100, 'RUN-STEP5')
  })

  it('feeds graph and time-based charts from the full timeline dataset', async () => {
    renderWithQueryClient()

    expect(await screen.findByTestId('account-flow-graph')).toHaveAttribute('data-count', '2')
    expect(screen.getByTestId('account-flow-graph')).toHaveAttribute('data-first-datetime', '2026-03-01T08:15:00Z')
    expect(screen.getByTestId('timeline-chart')).toHaveAttribute('data-count', '2')
    expect(screen.getByTestId('time-wheel')).toHaveAttribute('data-count', '2')
    expect(getResultsTimeline).toHaveBeenCalledWith('1234567890', 'RUN-STEP5')
  })
})
