import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { BankManager } from '@/components/BankManager'
import { useStore } from '@/store'

vi.mock('@/api', () => ({
  getBanks: vi.fn(async () => ([
    {
      key: 'scb',
      name: 'Siam Commercial Bank',
      logo_url: '/api/bank-logos/scb.svg',
      template_source: 'builtin',
      is_builtin: true,
      has_template: true,
    },
  ])),
  getBankLogoCatalog: vi.fn(async () => ([
    {
      key: 'scb',
      name: 'Siam Commercial Bank',
      logo_url: '/api/bank-logos/scb.svg',
      template_source: 'builtin',
      is_builtin: true,
      has_template: true,
      bank_type: 'thai_bank',
      template_badge: 'Template ready',
    },
    {
      key: 'baac',
      name: 'Bank for Agriculture and Agricultural Cooperatives',
      logo_url: '/api/bank-logos/baac.svg',
      template_source: 'registry',
      is_builtin: false,
      has_template: false,
      bank_type: 'thai_bank',
      template_badge: 'Logo ready / template pending',
      bank_name_th: 'ธนาคารเพื่อการเกษตรและสหกรณ์การเกษตร',
      bank_name_en: 'Bank for Agriculture and Agricultural Cooperatives',
      head_office_address: '2346 ถนนพหลโยธิน แขวงเสนานิคม เขตจตุจักร กรุงเทพฯ 10900',
    },
  ])),
  getBank: vi.fn(async () => null),
  createBank: vi.fn(async () => ({ status: 'ok', logo: { key: 'baac', logo_url: '/api/bank-logos/baac.svg' } })),
  deleteBank: vi.fn(async () => ({ status: 'ok' })),
  listMappingVariants: vi.fn(async () => ({ items: [], count: 0 })),
  promoteMappingVariant: vi.fn(async () => ({ status: 'ok', variant: { variant_id: 'VARIANT-1', trust_state: 'verified' } })),
  markMappingVariantRollbackReview: vi.fn(async () => ({ status: 'ok', variant: { variant_id: 'VARIANT-RISKY', trust_state: 'trusted', rollback_review_marked: true } })),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const { getBank, listMappingVariants, markMappingVariantRollbackReview, promoteMappingVariant } = await import('@/api')

function renderWithQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <BankManager />
    </QueryClientProvider>,
  )
}

describe('BankManager prepared bank logos', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useStore.getState().reset()
    useStore.setState({ operatorName: 'Case Reviewer' })
  })

  it('shows future-ready thai banks and pre-fills a template form when selected', async () => {
    renderWithQueryClient()

    await screen.findByText('Thai banks prepared')
    expect(screen.getByAltText('Bank for Agriculture and Agricultural Cooperatives logo')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Bank for Agriculture and Agricultural Cooperatives'))

    expect(await screen.findByDisplayValue('baac')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Bank for Agriculture and Agricultural Cooperatives')).toBeInTheDocument()
    expect(screen.getByText('Logo ready / template pending')).toBeInTheDocument()
    expect(screen.getByText('Reference Profile')).toBeInTheDocument()
    expect(screen.getByText('ธนาคารเพื่อการเกษตรและสหกรณ์การเกษตร')).toBeInTheDocument()
    expect(screen.getByText('2346 ถนนพหลโยธิน แขวงเสนานิคม เขตจตุจักร กรุงเทพฯ 10900')).toBeInTheDocument()
  })

  it('lists guarded template variants and promotes the next trust state', async () => {
    vi.mocked(getBank).mockResolvedValueOnce({
      key: 'scb',
      bank_name: 'Siam Commercial Bank',
      sheet_index: 0,
      header_row: 0,
      format_type: 'standard',
      amount_mode: 'signed',
      column_mapping: { date: ['วันที่'], description: ['รายการ'], amount: ['จำนวนเงิน'] },
      logo_url: '/api/bank-logos/scb.svg',
      template_source: 'builtin',
      is_builtin: true,
      has_template: true,
    })
    vi.mocked(listMappingVariants).mockResolvedValue({
      count: 2,
      auto_pass_summary: {
        mode: 'observe_only',
        total: 2,
        ready_observe_only: 0,
        blocked: 1,
        rollback_review: 1,
        would_auto_pass: 0,
        auto_pass_eligible: 0,
        top_blocked_reasons: [{ reason: 'not_trusted', count: 1 }],
        top_rollback_reasons: [],
      },
      items: [{
        variant_id: 'VARIANT-1',
        bank_key: 'scb',
        source_type: 'excel',
        sheet_name: 'Sheet1',
        header_row: 0,
        columns: ['วันที่', 'รายการ', 'จำนวนเงิน'],
        confirmed_mapping: { date: 'วันที่', description: 'รายการ', amount: 'จำนวนเงิน' },
        trust_state: 'candidate',
        confirmation_count: 2,
        correction_count: 0,
        correction_rate: 0,
        reviewer_count: 1,
        dry_run_summary: { valid_transaction_rows: 3 },
        auto_pass_gate: {
          mode: 'observe_only',
          status: 'blocked',
          would_auto_pass: false,
          auto_pass_eligible: false,
          blocked_reasons: ['not_trusted', 'insufficient_reviewers'],
          rollback_recommended: false,
          rollback_reasons: [],
        },
        updated_at: '2026-04-24T02:00:00Z',
      }, {
        variant_id: 'VARIANT-RISKY',
        bank_key: 'scb',
        source_type: 'excel',
        sheet_name: 'Sheet1',
        header_row: 0,
        columns: ['วันที่', 'รายการ', 'จำนวนเงิน'],
        confirmed_mapping: { date: 'วันที่', description: 'รายการ', amount: 'จำนวนเงิน' },
        trust_state: 'trusted',
        confirmation_count: 3,
        correction_count: 2,
        correction_rate: 0.67,
        reviewer_count: 2,
        dry_run_summary: { valid_transaction_rows: 3 },
        rollback_review_marked: false,
        auto_pass_gate: {
          mode: 'observe_only',
          status: 'rollback_review',
          would_auto_pass: false,
          auto_pass_eligible: false,
          blocked_reasons: ['correction_rate_high'],
          rollback_recommended: true,
          rollback_reasons: ['trusted_correction_rate_high'],
        },
        updated_at: '2026-04-24T03:00:00Z',
      }],
    })

    renderWithQueryClient()
    fireEvent.click(await screen.findByText('Siam Commercial Bank'))

    expect(await screen.findByText('Template Variants')).toBeInTheDocument()
    expect(await screen.findByText('VARIANT-1')).toBeInTheDocument()
    expect(await screen.findByText('VARIANT-RISKY')).toBeInTheDocument()
    expect(screen.getByText('2 confirmations')).toBeInTheDocument()
    expect(screen.getByText('Gate Summary')).toBeInTheDocument()
    expect(screen.getByText('2 total')).toBeInTheDocument()
    expect(screen.getByText('1 blocked')).toBeInTheDocument()
    expect(screen.getByText('1 rollback review')).toBeInTheDocument()
    expect(screen.getByText('Top blocker: not trusted (1)')).toBeInTheDocument()
    expect(screen.getAllByText('Auto-pass Gate')).toHaveLength(2)
    expect(screen.getAllByText('Observe only')).toHaveLength(3)
    expect(screen.getByText('not trusted')).toBeInTheDocument()
    expect(screen.getByText(/trusted correction rate high/)).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('Rollback review note'), {
      target: { value: 'correction rate exceeded gate' },
    })
    fireEvent.click(screen.getByRole('button', { name: /mark rollback review/i }))

    await waitFor(() => expect(markMappingVariantRollbackReview).toHaveBeenCalledWith(
      'VARIANT-RISKY',
      {
        reviewer: 'Case Reviewer',
        note: 'correction rate exceeded gate',
      },
    ))

    fireEvent.change(screen.getByPlaceholderText('Promotion note'), {
      target: { value: 'confirmed in two reviewed files' },
    })
    fireEvent.click(screen.getByRole('button', { name: /promote to verified/i }))

    await waitFor(() => expect(promoteMappingVariant).toHaveBeenCalledWith(
      'VARIANT-1',
      {
        trust_state: 'verified',
        reviewer: 'Case Reviewer',
        note: 'confirmed in two reviewed files',
      },
    ))
  })
})
