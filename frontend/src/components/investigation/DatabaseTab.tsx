
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
