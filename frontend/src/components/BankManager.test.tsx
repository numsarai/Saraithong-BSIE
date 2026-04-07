import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { BankManager } from '@/components/BankManager'

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
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

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
})
