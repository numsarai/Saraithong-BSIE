import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { BulkIntake } from '@/components/BulkIntake'
import { useStore } from '@/store'

vi.mock('@/api', () => ({
  processFolder: vi.fn(async () => ({
    run_id: '20260330_030000',
    run_dir: '/tmp/bulk_runs/20260330_030000',
    bundle_filename: 'case_bundle.zip',
    manifest_filename: 'case_manifest.json',
    analytics_filename: 'case_analytics.json',
    analytics_workbook_filename: 'case_analytics.xlsx',
    total_files: 2,
    processed_files: 1,
    skipped_files: 1,
    error_files: 0,
    review_required_files: 1,
    total_transactions: 10,
    total_reconciliation_mismatches: 2,
    chronology_issue_files: 1,
    drift_issue_files: 1,
    material_mismatch_files: 0,
    accounts: ['1234567890'],
    bank_counts: { SCB: 1 },
    reconciliation_counts: { VERIFIED: 0, PARTIAL: 0, FAILED: 1, INFERRED: 0, UNKNOWN: 0 },
    analytics: {
      overview: {
        processed_accounts: 1,
        flagged_accounts: 1,
        connected_groups: 1,
        bridge_accounts: 1,
        largest_counterparty_by_count: {
          counterparty_label: 'Alice (2222222222)',
          transaction_count: 3,
        },
      },
      top_counterparties_by_count: [
        {
          counterparty_id: '2222222222',
          counterparty_label: 'Alice (2222222222)',
          transaction_count: 3,
          total_value: 1200,
          subject_accounts: ['1234567890'],
        },
      ],
      bridge_accounts: [
        {
          counterparty_id: '2222222222',
          counterparty_label: 'Alice (2222222222)',
          subject_accounts: ['1234567890', '9999999999'],
          subject_account_count: 2,
          transaction_count: 4,
        },
      ],
      flagged_accounts: [
        {
          account: '1234567890',
          name: 'นาย ตัวอย่าง',
          bank: 'SCB',
          reason_codes: ['ambiguous_bank_detection', 'reconciliation_failed'],
        },
      ],
    },
    files: [
      {
        file_name: 'sample1.xlsx',
        file_path: '/case/sample1.xlsx',
        status: 'processed',
        account: '1234567890',
        name: 'นาย ตัวอย่าง',
        bank_name: 'SCB',
        bank_confidence: 0.61,
        bank_ambiguous: true,
        reconciliation_status: 'FAILED',
        num_transactions: 10,
        date_range: '2026-03-01 to 2026-03-10',
        reconciliation_mismatches: 2,
        chronology_issue_detected: true,
        chronological_mismatched_rows: 1,
        mismatches_reduced_by_sorting: 1,
        rounding_drift_rows: 1,
        material_mismatched_rows: 0,
        missing_time_rows: 0,
        duplicate_timestamp_rows: 0,
        recommended_check_mode: 'chronological',
        job_error: '',
      },
      {
        file_name: 'sample2.xlsx',
        file_path: '/case/sample2.xlsx',
        status: 'skipped',
        account: '',
        name: '',
        bank_name: '',
        reconciliation_status: '',
        num_transactions: 0,
        date_range: '',
        job_error: 'Could not infer subject account from filename or workbook header.',
      },
    ],
  })),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const { processFolder } = await import('@/api')

describe('BulkIntake', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useStore.getState().reset()
  })

  it('submits a folder path and renders the returned case summary', async () => {
    render(<BulkIntake />)

    fireEvent.change(screen.getByPlaceholderText('/absolute/path/to/case-folder'), {
      target: { value: '/cases/demo' },
    })
    fireEvent.click(screen.getByLabelText(/scan subfolders recursively/i))
    fireEvent.click(screen.getByRole('button', { name: /run bulk intake/i }))

    await waitFor(() => expect(processFolder).toHaveBeenCalledWith({
      folder_path: '/cases/demo',
      recursive: true,
    }))

    expect(await screen.findByText('20260330_030000')).toBeInTheDocument()
    expect(screen.getByText('sample1.xlsx')).toBeInTheDocument()
    expect(screen.getAllByText('FAILED').length).toBeGreaterThan(0)
    expect(screen.getByText('Needs review')).toBeInTheDocument()
    expect(screen.getByText('คำแนะนำสั้นสำหรับเคสนี้')).toBeInTheDocument()
    expect(screen.getByText(/ควรเปิดดูแบบ chronological/i)).toBeInTheDocument()
    expect(screen.getByText('Time Order')).toBeInTheDocument()
    expect(screen.getByText('Drift')).toBeInTheDocument()
    expect(screen.getByText('Case Risk Dashboard')).toBeInTheDocument()
    expect(screen.getAllByText('Alice (2222222222)').length).toBeGreaterThan(0)
    expect(screen.getByText(/could not infer subject account/i)).toBeInTheDocument()
    expect(screen.getAllByText('10').length).toBeGreaterThan(0)

    const csvLink = screen.getByRole('link', { name: /csv/i })
    expect(csvLink).toHaveAttribute('href', expect.stringContaining('/api/download-bulk/20260330_030000/bulk_summary.csv'))
    const analyticsJsonLink = screen.getByRole('link', { name: /analytics json/i })
    expect(analyticsJsonLink).toHaveAttribute('href', expect.stringContaining('/api/download-bulk/20260330_030000/case_analytics.json'))
    const manifestLink = screen.getByRole('link', { name: /manifest/i })
    expect(manifestLink).toHaveAttribute('href', expect.stringContaining('/api/download-bulk/20260330_030000/case_manifest.json'))
    const zipLink = screen.getByRole('link', { name: /case bundle/i })
    expect(zipLink).toHaveAttribute('href', expect.stringContaining('/api/download-bulk/20260330_030000/case_bundle.zip'))
  })

  it('opens processed accounts in the existing results step', async () => {
    render(<BulkIntake />)

    fireEvent.change(screen.getByPlaceholderText('/absolute/path/to/case-folder'), {
      target: { value: '/cases/demo' },
    })
    fireEvent.click(screen.getByRole('button', { name: /run bulk intake/i }))

    await screen.findByText('sample1.xlsx')
    fireEvent.click(screen.getByRole('button', { name: /open results/i }))

    expect(useStore.getState().page).toBe('main')
    expect(useStore.getState().step).toBe(5)
    expect(useStore.getState().account).toBe('1234567890')
  })

  it('filters to analyst-review rows only', async () => {
    render(<BulkIntake />)

    fireEvent.change(screen.getByPlaceholderText('/absolute/path/to/case-folder'), {
      target: { value: '/cases/demo' },
    })
    fireEvent.click(screen.getByRole('button', { name: /run bulk intake/i }))

    await screen.findByText('sample1.xlsx')
    fireEvent.change(screen.getByLabelText('Review Filter'), {
      target: { value: 'needs-review' },
    })

    await waitFor(() => expect(screen.queryByText('sample2.xlsx')).not.toBeInTheDocument())
    expect(screen.getByText('sample1.xlsx')).toBeInTheDocument()
    expect(screen.getByText(/showing/i)).toBeInTheDocument()
  })
})
