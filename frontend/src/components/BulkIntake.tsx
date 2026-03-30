import { useMemo, useState } from 'react'
import { Download, FolderSearch, RefreshCcw } from 'lucide-react'
import { toast } from 'sonner'

import { processFolder } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardTitle } from '@/components/ui/card'
import { fmtDateRange } from '@/lib/utils'
import { useStore } from '@/store'


function statusVariant(status: string): 'green' | 'red' | 'blue' | 'gray' {
  if (status === 'processed') return 'green'
  if (status === 'error') return 'red'
  if (status === 'skipped') return 'blue'
  return 'gray'
}

function needsAnalystReview(row: any) {
  if (row.status !== 'processed') return false
  const lowConfidence = Number(row.bank_confidence || 0) < 0.75
  const reconNeedsReview = ['FAILED', 'PARTIAL', 'INFERRED'].includes(String(row.reconciliation_status || ''))
  return Boolean(row.bank_ambiguous || lowConfidence || reconNeedsReview)
}

function getReconciliationSignals(row: any) {
  return {
    chronology: Boolean(row.chronology_issue_detected),
    drift: Number(row.rounding_drift_rows || 0) > 0,
    material: Number(row.material_mismatched_rows || 0) > 0,
    missingTime: Number(row.missing_time_rows || 0) > 0,
    duplicateTimestamps: Number(row.duplicate_timestamp_rows || 0) > 0,
  }
}

function getBulkReviewHint(row: any) {
  const signals = getReconciliationSignals(row)
  if (signals.material) return 'ควรตรวจยอดคงเหลือช่วงที่ผิดโดยตรง'
  if (signals.chronology) return 'ควรดูผลแบบเรียงตามเวลา'
  if (signals.drift) return 'มีส่วนต่างเล็กน้อยระดับเศษสตางค์'
  if (signals.missingTime) return 'บางแถวไม่มีเวลา'
  if (signals.duplicateTimestamps) return 'มีหลายรายการเวลาเดียวกัน'
  if (row.bank_ambiguous) return 'ควรยืนยันธนาคารและรูปแบบไฟล์'
  if (Number(row.bank_confidence || 0) < 0.75) return 'ความมั่นใจของ bank detect ต่ำ'
  return ''
}

function getQuickCaseGuidance(summary: any) {
  if (!summary) return ''
  if (Number(summary.material_mismatch_files || 0) > 0) {
    return 'มีบางไฟล์ที่ยอดคงเหลือผิดอย่างมีนัยสำคัญ ควรตรวจช่วงที่ผิดก่อนใช้อ้างอิงเชิงพิสูจน์'
  }
  if (Number(summary.chronology_issue_files || 0) > 0) {
    return 'มีไฟล์ที่น่าจะไม่เรียงตามเวลา ควรเปิดดูแบบ chronological ก่อนตัดสินว่า balance ผิดจริง'
  }
  if (Number(summary.drift_issue_files || 0) > 0) {
    return 'มีไฟล์ที่ต่างกันเพียงเล็กน้อยระดับเศษสตางค์ อาจเป็น rounding หรือ adjustment'
  }
  return 'ไม่พบสัญญาณความเสี่ยงเด่นจาก balance check ในระดับ bulk run'
}

export function BulkIntake() {
  const bulkSummary = useStore(s => s.bulkSummary)
  const setBulkSummary = useStore(s => s.setBulkSummary)
  const setAccount = useStore(s => s.setAccount)
  const setResults = useStore(s => s.setResults)
  const setPage = useStore(s => s.setPage)
  const setStep = useStore(s => s.setStep)
  const [folderPath, setFolderPath] = useState('')
  const [recursive, setRecursive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState('all')
  const [reviewFilter, setReviewFilter] = useState('all')
  const [search, setSearch] = useState('')

  const files = useMemo(() => bulkSummary?.files || [], [bulkSummary])
  const analytics = bulkSummary?.analytics || null
  const filteredFiles = useMemo(() => {
    const query = search.trim().toLowerCase()
    return files.filter((row: any) => {
      if (statusFilter !== 'all' && row.status !== statusFilter) return false
      if (reviewFilter === 'needs-review') {
        if (!needsAnalystReview(row)) return false
      }
      if (!query) return true
      const haystack = [
        row.file_name,
        row.account,
        row.name,
        row.bank_name,
        row.bank_key,
        row.reconciliation_status,
      ].join(' ').toLowerCase()
      return haystack.includes(query)
    })
  }, [files, reviewFilter, search, statusFilter])
  const runId = bulkSummary?.run_id || ''
  const bulkDl = (file: string, downloadName: string) =>
    `/api/download-bulk/${encodeURIComponent(runId)}/${encodeURIComponent(file).replace(/%2F/g, '/')}` +
    `?download_name=${encodeURIComponent(downloadName)}`

  const handleSubmit = async () => {
    if (!folderPath.trim()) {
      toast.error('Folder path is required')
      return
    }
    setLoading(true)
    try {
      const summary = await processFolder({
        folder_path: folderPath.trim(),
        recursive,
      })
      setBulkSummary(summary)
      setStatusFilter('all')
      setReviewFilter('all')
      setSearch('')
      toast.success(`Processed ${summary.processed_files}/${summary.total_files} files`)
    } catch (error: any) {
      toast.error(`Bulk intake failed: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const openResults = async (row: any) => {
    if (!row.account) return
    setAccount(row.account)
    setResults({
      account: row.account,
      meta: {
        ...(bulkSummary?.files?.find((item: any) => item.account === row.account) || {}),
      },
      entities: [],
      links: [],
    })
    setPage('main')
    setStep(5)
  }

  return (
    <div className="max-w-6xl space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-text">Bulk Folder Intake</h2>
          <p className="text-muted text-sm">
            Process a whole case folder of statement files and review which files were processed, skipped, or failed.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setBulkSummary(null)}>
          <RefreshCcw size={13} />
          Clear Summary
        </Button>
      </div>

      <Card className="space-y-4">
        <CardTitle>
          <FolderSearch size={16} />
          Case Folder
        </CardTitle>
        <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <label className="block">
            <div className="mb-1 text-xs font-semibold uppercase text-muted">Folder Path</div>
            <input
              value={folderPath}
              onChange={(event) => setFolderPath(event.target.value)}
              placeholder="/absolute/path/to/case-folder"
              className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none transition-colors focus:border-accent"
            />
          </label>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? 'Processing…' : 'Run Bulk Intake'}
          </Button>
        </div>
        <label className="flex items-center gap-2 text-sm text-text2">
          <input
            type="checkbox"
            checked={recursive}
            onChange={(event) => setRecursive(event.target.checked)}
            className="h-4 w-4 rounded border-border bg-surface2"
          />
          Scan subfolders recursively
        </label>
      </Card>

      {bulkSummary && (
        <>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3">
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Run ID</div>
              <div className="mt-1 font-mono text-sm text-text">{bulkSummary.run_id}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Processed</div>
              <div className="mt-1 text-xl font-bold text-success">{bulkSummary.processed_files}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Skipped</div>
              <div className="mt-1 text-xl font-bold text-accent">{bulkSummary.skipped_files}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Errors</div>
              <div className="mt-1 text-xl font-bold text-danger">{bulkSummary.error_files}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Accounts</div>
              <div className="mt-1 text-sm font-semibold text-text">
                {Array.isArray(bulkSummary.accounts) && bulkSummary.accounts.length > 0
                  ? bulkSummary.accounts.join(', ')
                  : '—'}
              </div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Needs Review</div>
              <div className="mt-1 text-xl font-bold text-warning">{bulkSummary.review_required_files ?? 0}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Transactions</div>
              <div className="mt-1 text-xl font-bold text-text">{bulkSummary.total_transactions ?? 0}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Balance Mismatches</div>
              <div className="mt-1 text-xl font-bold text-danger">{bulkSummary.total_reconciliation_mismatches ?? 0}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Time Order Issues</div>
              <div className="mt-1 text-xl font-bold text-warning">{bulkSummary.chronology_issue_files ?? 0}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Drift Files</div>
              <div className="mt-1 text-xl font-bold text-accent">{bulkSummary.drift_issue_files ?? 0}</div>
            </Card>
            <Card>
              <div className="text-[11px] uppercase text-muted font-semibold">Material Mismatch Files</div>
              <div className="mt-1 text-xl font-bold text-danger">{bulkSummary.material_mismatch_files ?? 0}</div>
            </Card>
          </div>

          <Card className="space-y-2">
            <CardTitle className="mb-0">คำแนะนำสั้นสำหรับเคสนี้</CardTitle>
            <p className="text-sm text-text2">{getQuickCaseGuidance(bulkSummary)}</p>
          </Card>

          <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr]">
            <Card className="space-y-3">
              <CardTitle className="mb-0">Bank Distribution</CardTitle>
              <div className="grid grid-cols-[repeat(auto-fit,minmax(130px,1fr))] gap-3">
                {Object.entries(bulkSummary.bank_counts || {}).map(([bank, count]) => (
                  <div key={bank} className="rounded-lg border border-border bg-surface2 px-3 py-2">
                    <div className="text-[11px] uppercase text-muted font-semibold">{bank}</div>
                    <div className="mt-1 text-lg font-bold text-text">{String(count)}</div>
                  </div>
                ))}
                {Object.keys(bulkSummary.bank_counts || {}).length === 0 && (
                  <div className="text-sm text-muted">No processed bank counts yet.</div>
                )}
              </div>
            </Card>

            <Card className="space-y-3">
              <CardTitle className="mb-0">Reconciliation Status</CardTitle>
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(bulkSummary.reconciliation_counts || {}).map(([status, count]) => (
                  <div key={status} className="rounded-lg border border-border bg-surface2 px-3 py-2">
                    <div className="text-[11px] uppercase text-muted font-semibold">{status}</div>
                    <div className="mt-1 text-lg font-bold text-text">{String(count)}</div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="mb-0">Case Summary Files</CardTitle>
              <div className="flex flex-wrap gap-2">
                <a
                  href={bulkDl(bulkSummary.manifest_filename || 'case_manifest.json', `bsie_case_manifest_${runId}.json`)}
                  download={`bsie_case_manifest_${runId}.json`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-accent transition-colors hover:border-accent"
                >
                  <Download size={13} />
                  Manifest
                </a>
                <a
                  href={bulkDl(bulkSummary.bundle_filename || 'case_bundle.zip', `bsie_case_bundle_${runId}.zip`)}
                  download={`bsie_case_bundle_${runId}.zip`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-accent transition-colors hover:border-accent"
                >
                  <Download size={13} />
                  Case Bundle
                </a>
                <a
                  href={bulkDl(bulkSummary.analytics_filename || 'case_analytics.json', `bsie_case_analytics_${runId}.json`)}
                  download={`bsie_case_analytics_${runId}.json`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-accent transition-colors hover:border-accent"
                >
                  <Download size={13} />
                  Analytics JSON
                </a>
                <a
                  href={bulkDl(bulkSummary.analytics_workbook_filename || 'case_analytics.xlsx', `bsie_case_analytics_${runId}.xlsx`)}
                  download={`bsie_case_analytics_${runId}.xlsx`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-accent transition-colors hover:border-accent"
                >
                  <Download size={13} />
                  Analytics Excel
                </a>
                <a
                  href={bulkDl('bulk_summary.csv', `bsie_bulk_${runId}.csv`)}
                  download={`bsie_bulk_${runId}.csv`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-accent transition-colors hover:border-accent"
                >
                  <Download size={13} />
                  CSV
                </a>
                <a
                  href={bulkDl('bulk_summary.xlsx', `bsie_bulk_${runId}.xlsx`)}
                  download={`bsie_bulk_${runId}.xlsx`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-accent transition-colors hover:border-accent"
                >
                  <Download size={13} />
                  Excel
                </a>
                <a
                  href={bulkDl('bulk_summary.json', `bsie_bulk_${runId}.json`)}
                  download={`bsie_bulk_${runId}.json`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-accent transition-colors hover:border-accent"
                >
                  <Download size={13} />
                  JSON
                </a>
              </div>
            </div>
            <p className="text-xs text-muted">
              Run directory: <span className="font-mono">{bulkSummary.run_dir}</span>
            </p>
          </Card>

          {analytics && (
            <div className="grid gap-3 lg:grid-cols-[1.1fr_1fr]">
              <Card className="space-y-3">
                <CardTitle className="mb-0">Case Risk Dashboard</CardTitle>
                <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-3">
                  <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
                    <div className="text-[11px] uppercase text-muted font-semibold">Flagged Accounts</div>
                    <div className="mt-1 text-lg font-bold text-warning">{analytics.overview?.flagged_accounts ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
                    <div className="text-[11px] uppercase text-muted font-semibold">Connected Groups</div>
                    <div className="mt-1 text-lg font-bold text-text">{analytics.overview?.connected_groups ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
                    <div className="text-[11px] uppercase text-muted font-semibold">Bridge Accounts</div>
                    <div className="mt-1 text-lg font-bold text-accent">{analytics.overview?.bridge_accounts ?? 0}</div>
                  </div>
                  <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
                    <div className="text-[11px] uppercase text-muted font-semibold">Processed Accounts</div>
                    <div className="mt-1 text-lg font-bold text-text">{analytics.overview?.processed_accounts ?? 0}</div>
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm">
                  <div className="text-[11px] uppercase text-muted font-semibold">Largest Counterparty By Count</div>
                  <div className="mt-1 font-semibold text-text">
                    {analytics.overview?.largest_counterparty_by_count?.counterparty_label || '—'}
                  </div>
                  <div className="text-xs text-muted">
                    {analytics.overview?.largest_counterparty_by_count?.transaction_count ?? 0} transactions
                  </div>
                </div>
              </Card>

              <Card className="space-y-3">
                <CardTitle className="mb-0">Flagged Accounts</CardTitle>
                <div className="space-y-2">
                  {(analytics.flagged_accounts || []).slice(0, 6).map((row: any) => (
                    <div key={row.account} className="rounded-lg border border-border bg-surface2 px-3 py-2">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="font-semibold text-text">{row.account}</div>
                          <div className="text-xs text-muted">{row.name || 'Unknown name'} · {row.bank || 'Unknown bank'}</div>
                        </div>
                        <Badge variant="red">Review</Badge>
                      </div>
                      <div className="mt-2 text-xs text-muted">{(row.reason_codes || []).join(', ') || 'No reason codes'}</div>
                    </div>
                  ))}
                  {(!analytics.flagged_accounts || analytics.flagged_accounts.length === 0) && (
                    <div className="text-sm text-muted">No flagged accounts in this case run.</div>
                  )}
                </div>
              </Card>
            </div>
          )}

          {analytics && (
            <div className="grid gap-3 lg:grid-cols-2">
              <Card className="space-y-3">
                <CardTitle className="mb-0">Top Counterparties By Count</CardTitle>
                <div className="space-y-2">
                  {(analytics.top_counterparties_by_count || []).slice(0, 8).map((row: any) => (
                    <div key={row.counterparty_id} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface2 px-3 py-2 text-sm">
                      <div>
                        <div className="font-semibold text-text">{row.counterparty_label}</div>
                        <div className="text-xs text-muted">{row.subject_accounts?.join(', ') || '—'}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-text">{row.transaction_count}</div>
                        <div className="text-xs text-muted">฿{Number(row.total_value || 0).toLocaleString()}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card className="space-y-3">
                <CardTitle className="mb-0">Bridge Accounts</CardTitle>
                <div className="space-y-2">
                  {(analytics.bridge_accounts || []).slice(0, 8).map((row: any) => (
                    <div key={row.counterparty_id} className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm">
                      <div className="font-semibold text-text">{row.counterparty_label}</div>
                      <div className="text-xs text-muted">{row.subject_accounts?.join(', ') || '—'}</div>
                      <div className="mt-1 text-xs text-text2">
                        Connected to {row.subject_account_count} subject accounts · {row.transaction_count} transactions
                      </div>
                    </div>
                  ))}
                  {(!analytics.bridge_accounts || analytics.bridge_accounts.length === 0) && (
                    <div className="text-sm text-muted">No bridge accounts detected yet.</div>
                  )}
                </div>
              </Card>
            </div>
          )}

          <Card className="space-y-4">
            <div className="flex flex-wrap items-end gap-3">
              <label className="block">
                <div className="mb-1 text-xs font-semibold uppercase text-muted">Status Filter</div>
                <select
                  aria-label="Status Filter"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent"
                >
                  <option value="all">All</option>
                  <option value="processed">Processed</option>
                  <option value="skipped">Skipped</option>
                  <option value="error">Error</option>
                </select>
              </label>

              <label className="block">
                <div className="mb-1 text-xs font-semibold uppercase text-muted">Review Filter</div>
                <select
                  aria-label="Review Filter"
                  value={reviewFilter}
                  onChange={(event) => setReviewFilter(event.target.value)}
                  className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent"
                >
                  <option value="all">All Files</option>
                  <option value="needs-review">Needs Analyst Review</option>
                </select>
              </label>

              <label className="min-w-[240px] flex-1">
                <div className="mb-1 text-xs font-semibold uppercase text-muted">Search</div>
                <input
                  aria-label="Search Bulk Files"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search file, account, name, or bank"
                  className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none transition-colors focus:border-accent"
                />
              </label>
            </div>
            <p className="text-xs text-muted">
              Showing {filteredFiles.length} of {files.length} files.
            </p>
          </Card>

          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse" style={{ minWidth: 1100 }}>
                <thead>
                  <tr className="bg-surface2">
                    {['File', 'Status', 'Account', 'Name', 'Bank', 'Reconciliation', 'Transactions', 'Date Range', 'Error', ''].map((heading) => (
                      <th key={heading} className="px-3 py-2 text-left text-[10px] font-semibold uppercase text-muted border-b border-border">
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredFiles.map((row: any) => (
                    <tr key={`${row.file_path}-${row.account}`} className="border-b border-border/40 hover:bg-accent/[0.04]">
                      <td className="px-3 py-2 text-text2">{row.file_name}</td>
                      <td className="px-3 py-2">
                        <Badge variant={statusVariant(row.status)}>{row.status || 'unknown'}</Badge>
                      </td>
                      <td className="px-3 py-2 font-mono text-text2">{row.account || '—'}</td>
                      <td className="px-3 py-2 text-text2">{row.name || '—'}</td>
                      <td className="px-3 py-2 text-text2">
                        {row.bank_name || row.bank_key || '—'}
                        {needsAnalystReview(row) ? (
                          <div className="mt-1 text-[10px] text-warning">Needs review</div>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-text2">
                        <div>{row.reconciliation_status || '—'}</div>
                        {row.status === 'processed' && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {getReconciliationSignals(row).chronology && <Badge variant="yellow">Time Order</Badge>}
                            {getReconciliationSignals(row).drift && <Badge variant="blue">Drift</Badge>}
                            {getReconciliationSignals(row).material && <Badge variant="red">Material</Badge>}
                          </div>
                        )}
                        {getBulkReviewHint(row) ? (
                          <div className="mt-1 text-[10px] text-muted">{getBulkReviewHint(row)}</div>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-text2">{row.num_transactions ?? '—'}</td>
                      <td className="px-3 py-2 text-muted">{fmtDateRange(row.date_range)}</td>
                      <td className="px-3 py-2 text-danger max-w-[280px] truncate">{row.job_error || '—'}</td>
                      <td className="px-3 py-2">
                        {row.status === 'processed' && row.account ? (
                          <Button size="sm" variant="ghost" onClick={() => openResults(row)}>
                            Open Results
                          </Button>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
