
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { fmtDate } from '@/lib/utils'

function formatValue(value: any) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  if (typeof value === 'string' && (value.includes('T') || /^\d{4}-\d{2}-\d{2}$/.test(value) || /^\d{1,2}[\/\-\s]\d{1,2}[\/\-\s]\d{4}$/.test(value))) {
    return fmtDate(value)
  }
  return String(value)
}

// StatCard removed — not used in this tab

function FieldBlock({ label, value, mono = false }: { label: string; value: any; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className={mono ? 'font-mono text-sm text-text break-all' : 'text-sm text-text whitespace-pre-wrap break-words'}>
        {formatValue(value)}
      </div>
    </div>
  )
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={[
        'rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent',
        props.className || '',
      ].join(' ')}
    />
  )
}

interface DatabaseTabProps {
  dbStatus: any
  dataHygiene: any
  backups: any[]
  selectedBackupFilename: string
  setSelectedBackupFilename: (value: string) => void
  selectedBackup: any
  backupPreview: any
  backupEnabled: boolean
  setBackupEnabled: (value: boolean) => void
  backupIntervalHours: string
  setBackupIntervalHours: (value: string) => void
  backupRetentionEnabled: boolean
  setBackupRetentionEnabled: (value: boolean) => void
  backupRetainCount: string
  setBackupRetainCount: (value: string) => void
  adminNote: string
  setAdminNote: (value: string) => void
  resetConfirmText: string
  setResetConfirmText: (value: string) => void
  restoreConfirmText: string
  setRestoreConfirmText: (value: string) => void
  backupSettingsData: any
  backupsData: any
  onSaveBackupSettings: () => void
  onCreateBackup: () => void
  onResetDatabase: () => void
  onRestoreDatabase: () => void
}

export function DatabaseTab({
  dbStatus,
  dataHygiene,
  backups,
  selectedBackupFilename,
  setSelectedBackupFilename,
  selectedBackup,
  backupPreview,
  backupEnabled,
  setBackupEnabled,
  backupIntervalHours,
  setBackupIntervalHours,
  backupRetentionEnabled,
  setBackupRetentionEnabled,
  backupRetainCount,
  setBackupRetainCount,
  adminNote,
  setAdminNote,
  resetConfirmText,
  setResetConfirmText,
  restoreConfirmText,
  setRestoreConfirmText,
  backupSettingsData,
  backupsData,
  onSaveBackupSettings,
  onCreateBackup,
  onResetDatabase,
  onRestoreDatabase,
}: DatabaseTabProps) {
  const hygieneStatus = dataHygiene?.overall_status || 'unknown'
  const hygieneBadge = hygieneStatus === 'blocked' ? 'red' : hygieneStatus === 'ready' ? 'green' : hygieneStatus === 'review_required' ? 'yellow' : 'gray'
  const hygieneSummary = dataHygiene?.summary || {}
  const hygieneChecks = dataHygiene?.checks || []
  const hygieneRecommendations = dataHygiene?.recommendations || []
  const repeatedFilenames = dataHygiene?.samples?.repeated_filenames || []
  const duplicateFingerprintFiles = dataHygiene?.samples?.duplicate_fingerprint_files || []

  return (
    <Card className="space-y-4">
      <CardTitle>Database Readiness</CardTitle>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {Object.entries(dbStatus?.key_record_counts || {}).map(([key, value]) => (
          <FieldBlock key={key} label={key.replaceAll('_', ' ')} value={value} />
        ))}
      </div>
      <div className="rounded-xl border border-border bg-surface2 p-4 text-sm text-text2 space-y-2">
        <div>สถานะปัจจุบันของโปรเจคนี้เป็นระบบฐานข้อมูลถาวรแล้ว และตอนนี้รองรับทั้ง ingest ซ้ำ, duplicate detection, parser run history, transaction search, review, audit log, และ reproducible export jobs.</div>
        <div>runtime ของโปรเจคนี้ถูกยุบให้เป็น local SQLite แบบถาวรแล้ว จึงไม่ต้องพึ่ง worker แยก, Redis, หรือ PostgreSQL สำหรับการใช้งานปกติในเครื่อง.</div>
      </div>

      <div className="space-y-3 rounded-xl border border-border bg-surface p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-text">Data Hygiene Audit</div>
            <div className="text-xs text-text2">Read-only checks for sample data, repeated processing, and duplicate evidence signals.</div>
          </div>
          <Badge variant={hygieneBadge as any}>{hygieneStatus.replaceAll('_', ' ')}</Badge>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <FieldBlock label="Sample-like Files" value={hygieneSummary.sample_like_files ?? '—'} />
          <FieldBlock label="Test Actor Files" value={hygieneSummary.test_actor_files ?? '—'} />
          <FieldBlock label="Duplicate Hash Groups" value={hygieneSummary.duplicate_file_hash_groups ?? '—'} />
          <FieldBlock label="Duplicate Fingerprints" value={hygieneSummary.duplicate_fingerprint_groups ?? '—'} />
          <FieldBlock label="Multiple Done Runs" value={hygieneSummary.files_with_multiple_done_runs ?? '—'} />
          <FieldBlock label="Non-done Run Transactions" value={hygieneSummary.transactions_on_non_done_runs ?? '—'} />
          <FieldBlock label="Queued Runs" value={hygieneSummary.parser_run_status_counts?.queued ?? 0} />
          <FieldBlock label="Failed Runs" value={hygieneSummary.parser_run_status_counts?.failed ?? 0} />
        </div>
        {hygieneRecommendations.length > 0 && (
          <div className="rounded-lg border border-border bg-surface2 p-3 text-sm text-text2">
            {hygieneRecommendations.map((item: string) => (
              <div key={item}>- {item}</div>
            ))}
          </div>
        )}
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface2 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Checks</div>
            <div className="space-y-2">
              {hygieneChecks.map((check: any) => (
                <div key={check.id} className="flex items-start justify-between gap-3 border-b border-border/60 pb-2 last:border-0 last:pb-0">
                  <div>
                    <div className="text-sm font-medium text-text">{check.label}</div>
                    <div className="text-xs text-text2">{check.detail}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant={check.severity === 'blocker' ? 'red' : check.severity === 'warning' ? 'yellow' : check.severity === 'ok' ? 'green' : 'gray'}>
                      {check.count}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-3 rounded-lg border border-border bg-surface2 p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted">Top Repeated / Duplicate Signals</div>
            <div className="max-h-52 overflow-auto rounded-lg border border-border bg-surface">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-surface2 text-left uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-3 py-2">Signal</th>
                    <th className="px-3 py-2">Files</th>
                    <th className="px-3 py-2">Hashes / Groups</th>
                  </tr>
                </thead>
                <tbody>
                  {repeatedFilenames.slice(0, 6).map((row: any) => (
                    <tr key={`${row.original_filename}-${row.uploaded_by}`} className="border-t border-border/60">
                      <td className="px-3 py-2">
                        <div className="font-medium text-text">{row.original_filename}</div>
                        <div className="text-muted">{row.uploaded_by}</div>
                      </td>
                      <td className="px-3 py-2">{row.files}</td>
                      <td className="px-3 py-2">{row.distinct_hashes}</td>
                    </tr>
                  ))}
                  {duplicateFingerprintFiles.slice(0, 4).map((row: any) => (
                    <tr key={`fp-${row.original_filename}`} className="border-t border-border/60">
                      <td className="px-3 py-2">
                        <div className="font-medium text-text">{row.original_filename}</div>
                        <div className="text-muted">duplicate fingerprint</div>
                      </td>
                      <td className="px-3 py-2">{row.duplicate_transactions}</td>
                      <td className="px-3 py-2">{row.duplicate_groups}</td>
                    </tr>
                  ))}
                  {repeatedFilenames.length === 0 && duplicateFingerprintFiles.length === 0 && (
                    <tr>
                      <td className="px-3 py-4 text-muted" colSpan={3}>No repeated or duplicate signals.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
        <div className="space-y-3 rounded-xl border border-border bg-surface p-4">
          <div className="text-sm font-semibold text-text">Backup / Reset / Restore</div>
          <div className="grid gap-3 md:grid-cols-[auto_minmax(120px,160px)_auto] md:items-end">
            <label className="flex items-center gap-2 text-sm text-text">
              <input
                type="checkbox"
                checked={backupEnabled}
                onChange={(event) => setBackupEnabled(event.target.checked)}
                className="h-4 w-4 rounded border-border bg-surface2"
              />
              Scheduled backup enabled
            </label>
            <TextInput
              type="number"
              min="1"
              step="1"
              value={backupIntervalHours}
              onChange={(event) => setBackupIntervalHours(event.target.value)}
              placeholder="Interval hours"
            />
            <Button variant="outline" onClick={onSaveBackupSettings}>Save Schedule</Button>
          </div>
          <div className="grid gap-3 md:grid-cols-[auto_minmax(120px,160px)] md:items-end">
            <label className="flex items-center gap-2 text-sm text-text">
              <input
                type="checkbox"
                checked={backupRetentionEnabled}
                onChange={(event) => setBackupRetentionEnabled(event.target.checked)}
                className="h-4 w-4 rounded border-border bg-surface2"
              />
              Retention enabled
            </label>
            <TextInput
              type="number"
              min="1"
              step="1"
              value={backupRetainCount}
              onChange={(event) => setBackupRetainCount(event.target.value)}
              placeholder="Keep last N backups"
            />
          </div>
          <div className="text-xs text-text2">
            Current schedule source: <span className="font-mono">{backupSettingsData?.source || backupsData?.settings?.source || '—'}</span>{' '}
            · effective format: <span className="font-mono">{backupSettingsData?.effective_backup_format || '—'}</span>{' '}
            · retention: <span className="font-mono">{backupSettingsData?.retention_enabled ? `keep ${backupSettingsData?.retain_count}` : 'off'}</span>
          </div>
          <TextInput
            value={adminNote}
            onChange={(event) => setAdminNote(event.target.value)}
            placeholder="Operation note for backup / reset / restore"
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={onCreateBackup}>Create Backup</Button>
            <Button variant="ghost" onClick={() => window.location.assign(`/api/download-backup/${encodeURIComponent(selectedBackupFilename)}?download_name=${encodeURIComponent(selectedBackupFilename)}`)} disabled={!selectedBackupFilename}>
              Download Selected Backup
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted">Reset Database</div>
              <div className="text-xs text-text2">Type: <span className="font-mono">{backupsData?.reset_confirmation_text || 'RESET BSIE DATABASE'}</span></div>
              <TextInput
                value={resetConfirmText}
                onChange={(event) => setResetConfirmText(event.target.value)}
                placeholder="Confirmation text"
              />
              <Button variant="danger" onClick={onResetDatabase}>Reset Current Database</Button>
            </div>
            <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted">Restore Backup</div>
              <div className="text-xs text-text2">Type: <span className="font-mono">{backupsData?.restore_confirmation_text || 'RESTORE BSIE DATABASE'}</span></div>
              <TextInput
                value={restoreConfirmText}
                onChange={(event) => setRestoreConfirmText(event.target.value)}
                placeholder="Confirmation text"
              />
              <Button variant="success" onClick={onRestoreDatabase} disabled={!selectedBackupFilename}>Restore Selected Backup</Button>
            </div>
          </div>
        </div>

        <div className="space-y-3 rounded-xl border border-border bg-surface p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-text">Available Backups</div>
            <Badge variant={backups.length > 0 ? 'green' : 'blue'}>{backups.length}</Badge>
          </div>
          <div className="max-h-[360px] overflow-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface2 text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-3 py-2">Backup</th>
                  <th className="px-3 py-2">Rows</th>
                  <th className="px-3 py-2">When</th>
                </tr>
              </thead>
              <tbody>
                {backups.length === 0 ? (
                  <tr>
                    <td className="px-3 py-4 text-muted" colSpan={3}>No backups yet.</td>
                  </tr>
                ) : backups.map((backup: any) => (
                  <tr
                    key={backup.filename}
                    className={[
                      'cursor-pointer border-t border-border/60',
                      selectedBackupFilename === backup.filename ? 'bg-accent/10' : 'hover:bg-surface2/80',
                    ].join(' ')}
                    onClick={() => setSelectedBackupFilename(backup.filename)}
                  >
                    <td className="px-3 py-2">
                      <div className="font-medium text-text">{backup.filename}</div>
                      <div className="text-xs text-muted">{backup.note || '—'}</div>
                    </td>
                    <td className="px-3 py-2">{formatValue(backup.total_rows)}</td>
                    <td className="px-3 py-2 text-xs text-text2">{formatValue(backup.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {selectedBackup && (
            <div className="grid gap-3 md:grid-cols-2">
              <FieldBlock label="Selected Backup" value={selectedBackup.filename} mono />
              <FieldBlock label="Created By" value={selectedBackup.created_by} />
              <FieldBlock label="Database Backend" value={selectedBackup.database_backend} />
              <FieldBlock label="Backup Format" value={selectedBackup.backup_format} />
              <FieldBlock label="Total Rows" value={selectedBackup.total_rows} />
            </div>
          )}
          {backupPreview && (
            <div className="space-y-3 rounded-lg border border-border bg-surface2 p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted">Restore Preview</div>
              <div className="grid gap-3 md:grid-cols-2">
                <FieldBlock label="Will Replace Current Data" value={backupPreview.will_replace_current_data ? 'Yes' : 'No'} />
                <FieldBlock label="Schema Version" value={backupPreview.schema_version} />
                <FieldBlock label="Backup Format" value={backupPreview.backup_format} />
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                {Object.entries(backupPreview.delta_table_counts || {}).slice(0, 9).map(([key, value]) => (
                  <FieldBlock key={key} label={`${key} delta`} value={value} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
