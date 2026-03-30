import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { InvestigationDesk } from '@/components/InvestigationDesk'

vi.mock('@/api', () => ({
  createDatabaseBackup: vi.fn(async () => ({ filename: 'backup.json', pruned_backups: [] })),
  createExportJob: vi.fn(async () => ({ id: 'EXP-1' })),
  getAccountDetail: vi.fn(async () => null),
  getAccounts: vi.fn(async () => ({ items: [] })),
  getAuditLogs: vi.fn(async () => ({
    items: [
      {
        id: 'AUD-1',
        object_type: 'transaction',
        object_id: 'TXN-001',
        action_type: 'update',
        changed_by: 'analyst',
        changed_at: '2026-03-30T23:30:00Z',
      },
    ],
  })),
  getDatabaseBackupPreview: vi.fn(async () => ({ counts: {} })),
  getDatabaseBackups: vi.fn(async () => ({ items: [], reset_confirmation_text: 'RESET BSIE DATABASE', restore_confirmation_text: 'RESTORE BSIE DATABASE' })),
  getDatabaseBackupSettings: vi.fn(async () => ({ enabled: false, interval_hours: 24, backup_format: 'auto', retention_enabled: false, retain_count: 20 })),
  getDbStatus: vi.fn(async () => ({ database_backend: 'postgresql', database_runtime_source: 'environment', table_count: 22, has_investigation_schema: true, key_record_counts: {}, tables: [], database_url_masked: 'postgresql://***' })),
  getDuplicates: vi.fn(async () => ({ items: [] })),
  getExportJobs: vi.fn(async () => ({ items: [] })),
  getFileDetail: vi.fn(async () => null),
  getFiles: vi.fn(async () => ({
    items: [
      {
        id: 'FILE-1',
        original_filename: 'sample.xlsx',
        import_status: 'stored',
        uploaded_at: '2026-03-30T23:30:00Z',
        file_hash_sha256: '1234567890abcdef1234567890abcdef',
      },
    ],
  })),
  getMatches: vi.fn(async () => ({ items: [] })),
  getParserRunDetail: vi.fn(async () => null),
  getParserRuns: vi.fn(async () => ({
    items: [
      {
        id: 'RUN-1',
        status: 'done',
        bank_detected: 'SCB',
        started_at: '2026-03-30T23:30:00Z',
      },
    ],
  })),
  getTransactionDetail: vi.fn(async () => null),
  reprocessParserRun: vi.fn(async () => ({ job_id: 'JOB-1' })),
  resetDatabase: vi.fn(async () => ({ status: 'ok' })),
  restoreDatabase: vi.fn(async () => ({ restored_backup: 'backup.json' })),
  updateDatabaseBackupSettings: vi.fn(async () => ({ enabled: false, interval_hours: 24, backup_format: 'auto', retention_enabled: false, retain_count: 20 })),
  reviewAccount: vi.fn(async () => ({ status: 'ok' })),
  reviewDuplicate: vi.fn(async () => ({ status: 'ok' })),
  reviewMatch: vi.fn(async () => ({ status: 'ok' })),
  reviewTransaction: vi.fn(async () => ({ status: 'ok' })),
  searchTransactionRecords: vi.fn(async () => ({ items: [] })),
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
      <InvestigationDesk />
    </QueryClientProvider>
  )
}

describe('InvestigationDesk date formatting', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders file, parser run, and audit dates as DD MM YYYY', async () => {
    renderWithQueryClient()

    fireEvent.click(await screen.findByRole('button', { name: 'Files' }))
    expect(await screen.findByText('31 03 2026')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Parser Runs' }))
    expect(await screen.findByText('31 03 2026')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Audit' }))
    expect(await screen.findByText('31 03 2026')).toBeInTheDocument()
  })
})
