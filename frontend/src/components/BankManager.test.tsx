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
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const { getBank, listMappingVariants, promoteMappingVariant } = await import('@/api')

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
      count: 1,
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
        updated_at: '2026-04-24T02:00:00Z',
      }],
    })

    renderWithQueryClient()
    fireEvent.click(await screen.findByText('Siam Commercial Bank'))

    expect(await screen.findByText('Template Variants')).toBeInTheDocument()
    expect(await screen.findByText('VARIANT-1')).toBeInTheDocument()
    expect(screen.getByText('2 confirmations')).toBeInTheDocument()

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
