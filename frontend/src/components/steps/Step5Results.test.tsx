import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { act } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

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

const { deleteOverride } = await import('@/api')

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
      operatorName: 'Case Reviewer',
      currentTab: 'transactions',
      results: null,
    })
  })

  it('renders table dates as DD MM YYYY and supports balance check mode switching', async () => {
    renderWithQueryClient()

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
      fireEvent.click(screen.getByRole('button', { name: 'entities' }))
    })
    expect(await screen.findByText('01 03 2026')).toBeInTheDocument()
    expect(screen.getByText('11 03 2026')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'links' }))
    })
    expect(await screen.findByText('05 03 2026')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'transactions' }))
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
})
