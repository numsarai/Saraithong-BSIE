import { startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react'
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  createDatabaseBackup,
  createExportJob,
  getAccountDetail,
  getAccounts,
  getAuditLogs,
  getLearningFeedbackLogs,
  getDatabaseBackupPreview,
  getDatabaseBackups,
  getDatabaseBackupSettings,
  getDbStatus,
  getDuplicates,
  getExportJobs,
  getFileDetail,
  getFiles,
  getMatches,
  getParserRunDetail,
  getParserRuns,
  getTransactionDetail,
  reprocessParserRun,
  resetDatabase,
  restoreDatabase,
  updateDatabaseBackupSettings,
  reviewAccount,
  reviewDuplicate,
  reviewMatch,
  reviewTransaction,
  searchTransactionRecords,
  getTimelineAggregate,
  getAlerts,
  getAlertSummary,
  reviewAlert as reviewAlertApi,
  getAccountFlows,
  getMatchedTransactions,
  traceFundPath,
} from '@/api'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TimelineChart } from '@/components/TimelineChart'
import { LinkChart } from '@/components/LinkChart'
import { toast } from 'sonner'
import { fmt, fmtDate } from '@/lib/utils'
import { normalizeOperatorName, useStore } from '@/store'

const TAB_IDS = ['database', 'files', 'runs', 'accounts', 'search', 'alerts', 'cross-account', 'link-chart', 'timeline', 'duplicates', 'matches', 'audit', 'exports'] as const

type TabId = (typeof TAB_IDS)[number]

type TransactionFilters = {
  q: string
  counterparty: string
  bank: string
  date_from: string
  date_to: string
  amount_min: string
  amount_max: string
  duplicate_status: string
  review_status: string
  file_id: string
  parser_run_id: string
}

const INITIAL_FILTERS: TransactionFilters = {
  q: '',
  counterparty: '',
  bank: '',
  date_from: '',
  date_to: '',
  amount_min: '',
  amount_max: '',
  duplicate_status: '',
  review_status: '',
  file_id: '',
  parser_run_id: '',
}

function formatValue(value: any) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  if (typeof value === 'string' && (value.includes('T') || /^\d{4}-\d{2}-\d{2}$/.test(value) || /^\d{1,2}[\/\-\s]\d{1,2}[\/\-\s]\d{4}$/.test(value))) {
    return fmtDate(value)
  }
  return String(value)
}

function compactHash(value: string) {
  return value ? `${value.slice(0, 16)}…` : '—'
}

function auditFeedbackBadgeVariant(status: string) {
  switch (String(status || '').toLowerCase()) {
    case 'corrected':
      return 'green'
    case 'confirmed':
      return 'blue'
    default:
      return 'gray'
  }
}

function StatCard({ label, value, tone = 'text-text' }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface px-4 py-3">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className={`text-lg font-bold ${tone}`}>{value}</div>
    </div>
  )
}

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

function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
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

function SelectInput(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={[
        'rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent',
        props.className || '',
      ].join(' ')}
    />
  )
}

export function InvestigationDesk() {
  const { t } = useTranslation()

  const TABS = [
    { id: 'database' as const, label: t('investigation.tabs.database') },
    { id: 'files' as const, label: t('investigation.tabs.files') },
    { id: 'runs' as const, label: t('investigation.tabs.runs') },
    { id: 'accounts' as const, label: t('investigation.tabs.accounts') },
    { id: 'search' as const, label: t('investigation.tabs.search') },
    { id: 'alerts' as const, label: t('investigation.tabs.alerts') },
    { id: 'cross-account' as const, label: t('investigation.tabs.crossAccount') },
    { id: 'link-chart' as const, label: t('investigation.tabs.linkChart') },
    { id: 'timeline' as const, label: t('investigation.tabs.timeline') },
    { id: 'duplicates' as const, label: t('investigation.tabs.duplicates') },
    { id: 'matches' as const, label: t('investigation.tabs.matches') },
    { id: 'audit' as const, label: t('investigation.tabs.audit') },
    { id: 'exports' as const, label: t('investigation.tabs.exports') },
  ]

  const AUDIT_QUICK_FILTERS = [
    { value: '', label: t('investigation.auditFilters.all') },
    { value: 'learning_feedback', label: t('investigation.auditFilters.learningFeedback') },
    { value: 'account', label: t('investigation.auditFilters.accountReviews') },
    { value: 'transaction', label: t('investigation.auditFilters.transactionReviews') },
  ]

  const operatorName = useStore(s => s.operatorName)
  const resolvedOperatorName = normalizeOperatorName(operatorName)
  const defaultCorrectionReason = `${resolvedOperatorName} correction`
  const [tab, setTab] = useState<TabId>('database')
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const [auditObjectType, setAuditObjectType] = useState('')
  const [auditObjectId, setAuditObjectId] = useState('')
  const deferredAuditObjectType = useDeferredValue(auditObjectType)
  const deferredAuditObjectId = useDeferredValue(auditObjectId)
  const [transactionFilters, setTransactionFilters] = useState<TransactionFilters>(INITIAL_FILTERS)
  const deferredTransactionFilters = useDeferredValue(transactionFilters)
  const [selectedFileId, setSelectedFileId] = useState('')
  const [selectedRunId, setSelectedRunId] = useState('')
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [selectedTransactionId, setSelectedTransactionId] = useState('')
  const [selectedBackupFilename, setSelectedBackupFilename] = useState('')
  const [adminNote, setAdminNote] = useState('')
  const [crossAccountSelected, setCrossAccountSelected] = useState('')
  const [crossAccountTarget, setCrossAccountTarget] = useState('')
  const [pathFrom, setPathFrom] = useState('')
  const [pathTo, setPathTo] = useState('')
  const [backupEnabled, setBackupEnabled] = useState(false)
  const [backupIntervalHours, setBackupIntervalHours] = useState('24')
  const [backupFormat, setBackupFormat] = useState('json')
  const [backupRetentionEnabled, setBackupRetentionEnabled] = useState(false)
  const [backupRetainCount, setBackupRetainCount] = useState('20')
  const [resetConfirmText, setResetConfirmText] = useState('')
  const [restoreConfirmText, setRestoreConfirmText] = useState('')
  const [accountEdit, setAccountEdit] = useState({ account_holder_name: '', bank_name: '', notes: '', reason: defaultCorrectionReason })
  const [transactionEdit, setTransactionEdit] = useState({ transaction_type: '', counterparty_name_normalized: '', review_status: '', reason: defaultCorrectionReason })
  const client = useQueryClient()

  const dbStatusQuery = useQuery({
    queryKey: ['investigation', 'db-status'],
    queryFn: () => getDbStatus(),
  })
  const backupsQuery = useQuery({
    queryKey: ['investigation', 'backups'],
    queryFn: () => getDatabaseBackups(),
  })
  const backupSettingsQuery = useQuery({
    queryKey: ['investigation', 'backup-settings'],
    queryFn: () => getDatabaseBackupSettings(),
  })
  const backupPreviewQuery = useQuery({
    queryKey: ['investigation', 'backup-preview', selectedBackupFilename],
    queryFn: () => getDatabaseBackupPreview(selectedBackupFilename),
    enabled: !!selectedBackupFilename,
  })
  const filesQuery = useQuery({
    queryKey: ['investigation', 'files'],
    queryFn: () => getFiles(),
    enabled: tab === 'files',
  })
  const fileDetailQuery = useQuery({
    queryKey: ['investigation', 'file-detail', selectedFileId],
    queryFn: () => getFileDetail(selectedFileId),
    enabled: !!selectedFileId,
  })
  const runsQuery = useQuery({
    queryKey: ['investigation', 'runs'],
    queryFn: () => getParserRuns(),
    enabled: tab === 'runs',
  })
  const runDetailQuery = useQuery({
    queryKey: ['investigation', 'run-detail', selectedRunId],
    queryFn: () => getParserRunDetail(selectedRunId),
    enabled: !!selectedRunId,
  })
  const accountsQuery = useQuery({
    queryKey: ['investigation', 'accounts', deferredQuery],
    queryFn: () => getAccounts(deferredQuery),
    enabled: tab === 'accounts',
  })
  const accountDetailQuery = useQuery({
    queryKey: ['investigation', 'account-detail', selectedAccountId],
    queryFn: () => getAccountDetail(selectedAccountId),
    enabled: !!selectedAccountId,
  })
  const searchQuery = useQuery({
    queryKey: ['investigation', 'search', deferredTransactionFilters],
    queryFn: () => searchTransactionRecords({ ...deferredTransactionFilters, limit: 100 }),
    enabled: tab === 'search',
  })
  const transactionDetailQuery = useQuery({
    queryKey: ['investigation', 'transaction-detail', selectedTransactionId],
    queryFn: () => getTransactionDetail(selectedTransactionId),
    enabled: !!selectedTransactionId,
  })
  const duplicatesQuery = useQuery({
    queryKey: ['investigation', 'duplicates'],
    queryFn: () => getDuplicates(),
    enabled: tab === 'duplicates',
  })
  const matchesQuery = useQuery({
    queryKey: ['investigation', 'matches'],
    queryFn: () => getMatches(),
    enabled: tab === 'matches',
  })
  const auditQuery = useQuery({
    queryKey: ['investigation', 'audit', deferredAuditObjectType, deferredAuditObjectId],
    queryFn: () => getAuditLogs({ object_type: deferredAuditObjectType, object_id: deferredAuditObjectId, limit: 100 }),
    enabled: tab === 'audit',
  })
  const learningFeedbackQuery = useQuery({
    queryKey: ['investigation', 'learning-feedback-summary'],
    queryFn: () => getLearningFeedbackLogs({ limit: 200 }),
    enabled: tab === 'audit',
  })
  const exportQuery = useQuery({
    queryKey: ['investigation', 'exports'],
    queryFn: () => getExportJobs(),
    enabled: tab === 'exports',
  })
  const alertsQuery = useQuery({
    queryKey: ['investigation', 'alerts'],
    queryFn: () => getAlerts({ limit: 500 }),
    enabled: tab === 'alerts',
    staleTime: 15_000,
  })
  const alertSummaryQuery = useQuery({
    queryKey: ['investigation', 'alert-summary'],
    queryFn: () => getAlertSummary(),
    enabled: tab === 'alerts',
    staleTime: 15_000,
  })
  const alertItems = alertsQuery.data?.items || []
  const alertSummary = alertSummaryQuery.data || {}

  const crossFlowQuery = useQuery({
    queryKey: ['investigation', 'cross-account-flows', crossAccountSelected],
    queryFn: () => getAccountFlows(crossAccountSelected),
    enabled: tab === 'cross-account' && !!crossAccountSelected,
    staleTime: 30_000,
  })
  const crossMatchQuery = useQuery({
    queryKey: ['investigation', 'cross-account-match', crossAccountSelected, crossAccountTarget],
    queryFn: () => getMatchedTransactions(crossAccountSelected, crossAccountTarget),
    enabled: tab === 'cross-account' && !!crossAccountSelected && !!crossAccountTarget,
  })
  const pathTraceQuery = useQuery({
    queryKey: ['investigation', 'path-trace', pathFrom, pathTo],
    queryFn: () => traceFundPath(pathFrom, pathTo),
    enabled: false, // Manual trigger only
  })

  const timelineAggQuery = useQuery({
    queryKey: ['investigation', 'timeline-aggregate', deferredTransactionFilters],
    queryFn: () => getTimelineAggregate(deferredTransactionFilters),
    enabled: tab === 'timeline',
    staleTime: 30_000,
  })
  const timelineAggItems = useMemo(() => {
    const items = timelineAggQuery.data?.items || []
    // Convert aggregated data to transaction-like rows for TimelineChart
    return items.flatMap((d: any) => {
      const rows: any[] = []
      if (d.in_count > 0) rows.push({ date: d.date, amount: d.in_total, direction: 'IN' })
      if (d.out_count > 0) rows.push({ date: d.date, amount: -d.out_total, direction: 'OUT' })
      return rows
    })
  }, [timelineAggQuery.data])

  const currentRows = useMemo(() => {
    switch (tab) {
      case 'files':
        return filesQuery.data?.items || []
      case 'runs':
        return runsQuery.data?.items || []
      case 'accounts':
        return accountsQuery.data?.items || []
      case 'search':
        return searchQuery.data?.items || []
      case 'duplicates':
        return duplicatesQuery.data?.items || []
      case 'matches':
        return matchesQuery.data?.items || []
      case 'audit':
        return auditQuery.data?.items || []
      case 'exports':
        return exportQuery.data?.items || []
      default:
        return []
    }
  }, [
    tab,
    filesQuery.data,
    runsQuery.data,
    accountsQuery.data,
    searchQuery.data,
    duplicatesQuery.data,
    matchesQuery.data,
    auditQuery.data,
    exportQuery.data,
  ])

  const learningFeedbackSummary = useMemo(() => {
    const rows = learningFeedbackQuery.data?.items || []
    const domainCounts = new Map<string, number>()
    const statusCounts = new Map<string, number>()

    for (const row of rows) {
      const domain = String(row.extra_context_json?.learning_domain || 'unknown')
      const status = String(row.extra_context_json?.feedback_status || 'unknown')
      domainCounts.set(domain, (domainCounts.get(domain) || 0) + 1)
      statusCounts.set(status, (statusCounts.get(status) || 0) + 1)
    }

    const topDomains = Array.from(domainCounts.entries())
      .sort((left, right) => right[1] - left[1])
      .slice(0, 4)
      .map(([domain, count]) => `${domain} (${count})`)

    return {
      total: rows.length,
      corrected: statusCounts.get('corrected') || 0,
      confirmed: statusCounts.get('confirmed') || 0,
      accepted: statusCounts.get('accepted') || 0,
      topDomains,
      lastUpdated: rows[0]?.changed_at || '',
    }
  }, [learningFeedbackQuery.data])

  const refreshAll = () => {
    void client.invalidateQueries({ queryKey: ['investigation'] })
  }

  const handleExport = async (exportType: string) => {
    try {
      await createExportJob({
        export_type: exportType,
        filters: exportType === 'graph' ? {
          ...(transactionFilters.parser_run_id ? { parser_run_id: transactionFilters.parser_run_id } : {}),
          ...(transactionFilters.file_id ? { file_id: transactionFilters.file_id } : {}),
          ...(transactionFilters.bank ? { bank: transactionFilters.bank } : {}),
        } : {},
        created_by: resolvedOperatorName,
      })
      toast.success(`${exportType} export created`)
      startTransition(() => setTab('exports'))
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleDuplicateReview = async (groupId: string, decision: string) => {
    try {
      await reviewDuplicate(groupId, { decision_value: decision, reviewer: resolvedOperatorName, reviewer_note: '' })
      toast.success(`Duplicate group ${decision}`)
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleMatchReview = async (matchId: string, decision: string) => {
    try {
      await reviewMatch(matchId, { decision_value: decision, reviewer: resolvedOperatorName, reviewer_note: '' })
      toast.success(`Match ${decision}`)
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleAccountSave = async () => {
    if (!selectedAccountId) return
    try {
      await reviewAccount(selectedAccountId, {
        reviewer: resolvedOperatorName,
        reason: accountEdit.reason,
        changes: {
          account_holder_name: accountEdit.account_holder_name || undefined,
          bank_name: accountEdit.bank_name || undefined,
          notes: accountEdit.notes || undefined,
        },
      })
      toast.success('Account updated with audit trail')
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleTransactionSave = async () => {
    if (!selectedTransactionId) return
    try {
      await reviewTransaction(selectedTransactionId, {
        reviewer: resolvedOperatorName,
        reason: transactionEdit.reason,
        changes: {
          transaction_type: transactionEdit.transaction_type || undefined,
          counterparty_name_normalized: transactionEdit.counterparty_name_normalized || undefined,
          review_status: transactionEdit.review_status || undefined,
        },
      })
      toast.success('Transaction updated with audit trail')
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleReprocess = async () => {
    if (!selectedRunId) return
    try {
      const payload = await reprocessParserRun(selectedRunId, {
        reviewer: resolvedOperatorName,
        reviewer_note: 'reprocess from database admin',
        decision_value: 'reprocess',
      })
      toast.success(`Reprocess queued: ${payload.job_id}`)
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleCreateBackup = async () => {
    try {
      const payload = await createDatabaseBackup({
        operator: resolvedOperatorName,
        note: adminNote || 'manual backup from investigation admin',
        backup_format: backupFormat,
      })
      setSelectedBackupFilename(payload.filename)
      toast.success(`Backup created: ${payload.filename}${payload.pruned_backups?.length ? ` · pruned ${payload.pruned_backups.length}` : ''}`)
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleSaveBackupSettings = async () => {
    try {
      const payload = await updateDatabaseBackupSettings({
        enabled: backupEnabled,
        interval_hours: Number(backupIntervalHours || 24),
        backup_format: backupFormat,
        retention_enabled: backupRetentionEnabled,
        retain_count: Number(backupRetainCount || 20),
        updated_by: resolvedOperatorName,
      })
      setBackupEnabled(Boolean(payload.enabled))
      setBackupIntervalHours(String(payload.interval_hours))
      setBackupFormat(String(payload.backup_format || 'json'))
      setBackupRetentionEnabled(Boolean(payload.retention_enabled))
      setBackupRetainCount(String(payload.retain_count))
      toast.success('Backup schedule updated')
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleResetDatabase = async () => {
    const expected = backupsQuery.data?.reset_confirmation_text || 'RESET BSIE DATABASE'
    if (resetConfirmText.trim() !== expected) {
      toast.error(`Type exactly: ${expected}`)
      return
    }
    if (!window.confirm('This will clear the current database after taking a safety backup. Continue?')) return
    try {
      const payload = await resetDatabase({
        confirm_text: resetConfirmText,
        operator: resolvedOperatorName,
        note: adminNote || 'manual database reset from investigation admin',
        create_pre_reset_backup: true,
      })
      toast.success(`Database reset complete${payload.pre_reset_backup ? ` — backup: ${payload.pre_reset_backup.filename}` : ''}`)
      setResetConfirmText('')
      setSelectedBackupFilename('')
      setSelectedAccountId('')
      setSelectedFileId('')
      setSelectedRunId('')
      setSelectedTransactionId('')
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const handleRestoreDatabase = async () => {
    const expected = backupsQuery.data?.restore_confirmation_text || 'RESTORE BSIE DATABASE'
    if (!selectedBackupFilename) {
      toast.error('Select a backup first')
      return
    }
    if (restoreConfirmText.trim() !== expected) {
      toast.error(`Type exactly: ${expected}`)
      return
    }
    if (!window.confirm(`Restore backup ${selectedBackupFilename}? Current data will be replaced after a safety backup.`)) return
    try {
      const payload = await restoreDatabase({
        backup_filename: selectedBackupFilename,
        confirm_text: restoreConfirmText,
        operator: resolvedOperatorName,
        note: adminNote || `manual restore from ${selectedBackupFilename}`,
        create_pre_restore_backup: true,
      })
      toast.success(`Database restored from ${payload.restored_backup}`)
      setRestoreConfirmText('')
      refreshAll()
    } catch (error: any) {
      toast.error(error.message)
    }
  }

  const dbStatus = dbStatusQuery.data
  const backups = backupsQuery.data?.items || []
  const accountDetail = accountDetailQuery.data
  const transactionDetail = transactionDetailQuery.data
  const fileDetail = fileDetailQuery.data
  const runDetail = runDetailQuery.data
  const backupPreview = backupPreviewQuery.data
  const selectedBackup = useMemo(
    () => backups.find((item: any) => item.filename === selectedBackupFilename),
    [backups, selectedBackupFilename],
  )

  useEffect(() => {
    if (!backupSettingsQuery.data) return
    setBackupEnabled(Boolean(backupSettingsQuery.data.enabled))
    setBackupIntervalHours(String(backupSettingsQuery.data.interval_hours ?? 24))
    setBackupFormat(String(backupSettingsQuery.data.backup_format || 'json'))
    setBackupRetentionEnabled(Boolean(backupSettingsQuery.data.retention_enabled))
    setBackupRetainCount(String(backupSettingsQuery.data.retain_count ?? 20))
  }, [backupSettingsQuery.data])

  useEffect(() => {
    if (!accountDetail) return
    setAccountEdit({
      account_holder_name: accountDetail.account_holder_name || '',
      bank_name: accountDetail.bank_name || '',
      notes: accountDetail.notes || '',
      reason: `${resolvedOperatorName} correction`,
    })
  }, [accountDetail])

  useEffect(() => {
    if (!transactionDetail) return
    setTransactionEdit({
      transaction_type: transactionDetail.transaction_type || '',
      counterparty_name_normalized: transactionDetail.counterparty_name_normalized || '',
      review_status: transactionDetail.review_status || '',
      reason: `${resolvedOperatorName} correction`,
    })
  }, [transactionDetail])

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-lg font-bold text-text">Investigation Admin</h2>
          <p className="text-sm text-muted">
            Inspect persisted evidence, review parser history, correct records with audit logs, and generate graph/i2 exports.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={refreshAll}>Refresh</Button>
          <Button variant="success" onClick={() => handleExport('graph')}>Graph Export</Button>
        </div>
      </div>

      <Card className="space-y-4">
        <CardTitle>Database Status</CardTitle>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-3">
          <StatCard label="Backend" value={dbStatus?.database_backend || '—'} tone={dbStatus?.database_backend === 'sqlite' ? 'text-success' : 'text-accent'} />
          <StatCard label="Runtime Source" value={dbStatus?.database_runtime_source || '—'} />
          <StatCard label="Tables" value={dbStatus?.table_count ?? '—'} />
          <StatCard label="Files" value={dbStatus?.key_record_counts?.files ?? '—'} />
          <StatCard label="Transactions" value={dbStatus?.key_record_counts?.transactions ?? '—'} />
          <StatCard label="Accounts" value={dbStatus?.key_record_counts?.accounts ?? '—'} />
          <StatCard label="Schema Ready" value={dbStatus?.has_investigation_schema ? 'Yes' : 'No'} tone={dbStatus?.has_investigation_schema ? 'text-success' : 'text-danger'} />
        </div>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,1fr)]">
          <FieldBlock label="Database URL" value={dbStatus?.database_url_masked || '—'} mono />
          <FieldBlock label="Tables" value={Array.isArray(dbStatus?.tables) ? dbStatus.tables.join(', ') : '—'} />
        </div>
      </Card>

      <div className="flex flex-wrap gap-2">
        {TABS.map((item) => (
          <button
            key={item.id}
            onClick={() => startTransition(() => setTab(item.id))}
            className={[
              'rounded-full border px-3 py-1.5 text-sm transition-all',
              tab === item.id ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-surface text-muted hover:border-accent/40 hover:text-text',
            ].join(' ')}
          >
            {item.label}
          </button>
        ))}
      </div>

      {(tab === 'accounts' || tab === 'audit') && (
        <Card>
          <CardTitle>{tab === 'accounts' ? 'Account Query' : 'Audit Object Filter'}</CardTitle>
          {tab === 'accounts' ? (
            <TextInput
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search account number, holder, or bank"
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              <SelectInput value={auditObjectType} onChange={(event) => setAuditObjectType(event.target.value)}>
                {AUDIT_QUICK_FILTERS.map((item) => (
                  <option key={item.label} value={item.value}>{item.label}</option>
                ))}
              </SelectInput>
              <TextInput
                value={auditObjectId}
                onChange={(event) => setAuditObjectId(event.target.value)}
                placeholder="Optional object_id filter"
              />
            </div>
          )}
          {tab === 'audit' && (
            <div className="mt-3 space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted">Quick Filters</div>
              <div className="flex flex-wrap gap-2">
                {AUDIT_QUICK_FILTERS.map((item) => (
                  <Button
                    key={item.label}
                    size="sm"
                    variant={auditObjectType === item.value ? 'outline' : 'ghost'}
                    onClick={() => setAuditObjectType(item.value)}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
              <div className="text-xs text-text2">
                Use <span className="font-mono">learning_feedback</span> to inspect what BSIE learned from confirmations and review corrections.
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === 'audit' && (
        <Card className="space-y-3">
          <CardTitle>Learning Feedback Summary</CardTitle>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-3">
            <StatCard label="Signals" value={learningFeedbackSummary.total} />
            <StatCard label="Corrected" value={learningFeedbackSummary.corrected} tone="text-success" />
            <StatCard label="Confirmed" value={learningFeedbackSummary.confirmed} tone="text-accent" />
            <StatCard label="Accepted" value={learningFeedbackSummary.accepted} tone="text-text2" />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <FieldBlock label="Top Learning Domains" value={learningFeedbackSummary.topDomains.length ? learningFeedbackSummary.topDomains.join(' · ') : '—'} />
            <FieldBlock label="Latest Learning Signal" value={learningFeedbackSummary.lastUpdated || '—'} />
          </div>
        </Card>
      )}

      {(tab === 'search' || tab === 'timeline') && (
        <Card className="space-y-3">
          <CardTitle>Transaction Query Builder</CardTitle>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <TextInput value={transactionFilters.q} onChange={(event) => setTransactionFilters((state) => ({ ...state, q: event.target.value }))} placeholder="Description / reference" />
            <TextInput value={transactionFilters.counterparty} onChange={(event) => setTransactionFilters((state) => ({ ...state, counterparty: event.target.value }))} placeholder="Counterparty name/account" />
            <TextInput value={transactionFilters.bank} onChange={(event) => setTransactionFilters((state) => ({ ...state, bank: event.target.value }))} placeholder="Bank" />
            <TextInput value={transactionFilters.file_id} onChange={(event) => setTransactionFilters((state) => ({ ...state, file_id: event.target.value }))} placeholder="File ID" />
            <TextInput value={transactionFilters.parser_run_id} onChange={(event) => setTransactionFilters((state) => ({ ...state, parser_run_id: event.target.value }))} placeholder="Parser Run ID" />
            <TextInput type="date" value={transactionFilters.date_from} onChange={(event) => setTransactionFilters((state) => ({ ...state, date_from: event.target.value }))} />
            <TextInput type="date" value={transactionFilters.date_to} onChange={(event) => setTransactionFilters((state) => ({ ...state, date_to: event.target.value }))} />
            <div className="grid grid-cols-2 gap-2">
              <TextInput value={transactionFilters.amount_min} onChange={(event) => setTransactionFilters((state) => ({ ...state, amount_min: event.target.value }))} placeholder="Amount min" />
              <TextInput value={transactionFilters.amount_max} onChange={(event) => setTransactionFilters((state) => ({ ...state, amount_max: event.target.value }))} placeholder="Amount max" />
            </div>
            <SelectInput value={transactionFilters.duplicate_status} onChange={(event) => setTransactionFilters((state) => ({ ...state, duplicate_status: event.target.value }))}>
              <option value="">Duplicate status</option>
              <option value="unique">unique</option>
              <option value="exact_duplicate">exact_duplicate</option>
              <option value="probable_duplicate">probable_duplicate</option>
              <option value="overlap_duplicate">overlap_duplicate</option>
              <option value="similar_conflict">similar_conflict</option>
            </SelectInput>
            <SelectInput value={transactionFilters.review_status} onChange={(event) => setTransactionFilters((state) => ({ ...state, review_status: event.target.value }))}>
              <option value="">Review status</option>
              <option value="pending">pending</option>
              <option value="needs_review">needs_review</option>
              <option value="reviewed">reviewed</option>
            </SelectInput>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setTransactionFilters(INITIAL_FILTERS)}>Clear Filters</Button>
            </div>
          </div>
        </Card>
      )}

      {tab === 'exports' && (
        <Card>
          <CardTitle>Reproducible Exports</CardTitle>
          <div className="flex flex-wrap gap-2">
            {[
              ['transactions', 'Transactions CSV/XLSX'],
              ['duplicates', 'Duplicate Review Report'],
              ['unresolved_matches', 'Unresolved Matches'],
              ['corrected_transactions', 'Corrected Transactions'],
              ['graph', 'Graph / i2 Export'],
            ].map(([key, label]) => (
              <Button key={key} variant="ghost" onClick={() => handleExport(key)}>
                {label}
              </Button>
            ))}
          </div>
        </Card>
      )}

      {tab === 'alerts' && (
        <div className="space-y-4">
          {/* Summary cards */}
          <div className="grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-3">
            <StatCard label={t('investigation.alerts.total')} value={alertSummary.total ?? 0} />
            <div className="rounded-xl border border-red-800/40 bg-red-900/20 px-3 py-2 text-center">
              <div className="text-lg font-bold text-red-400">{alertSummary.critical_count ?? 0}</div>
              <div className="text-[10px] text-red-400/70 uppercase font-semibold">{t('investigation.alerts.critical')}</div>
            </div>
            <div className="rounded-xl border border-orange-800/40 bg-orange-900/20 px-3 py-2 text-center">
              <div className="text-lg font-bold text-orange-400">{alertSummary.high_count ?? 0}</div>
              <div className="text-[10px] text-orange-400/70 uppercase font-semibold">{t('investigation.alerts.high')}</div>
            </div>
            <StatCard label={t('investigation.alerts.newAlerts')} value={alertSummary.new_count ?? 0} />
          </div>

          {/* Alert list */}
          {alertItems.length > 0 ? (
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted text-left">
                      <th className="px-2 py-2 font-semibold">{t('investigation.alerts.severity')}</th>
                      <th className="px-2 py-2 font-semibold">{t('investigation.alerts.ruleType')}</th>
                      <th className="px-2 py-2 font-semibold">{t('investigation.alerts.summary')}</th>
                      <th className="px-2 py-2 font-semibold">{t('investigation.alerts.confidence')}</th>
                      <th className="px-2 py-2 font-semibold">{t('investigation.alerts.status')}</th>
                      <th className="px-2 py-2 font-semibold">{t('investigation.alerts.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alertItems.map((alert: any) => {
                      const sevColor = alert.severity === 'critical' ? 'text-red-400 bg-red-900/30'
                        : alert.severity === 'high' ? 'text-orange-400 bg-orange-900/30'
                        : alert.severity === 'medium' ? 'text-yellow-400 bg-yellow-900/30'
                        : 'text-blue-400 bg-blue-900/30'
                      const statusColor = alert.status === 'new' ? 'text-red-400'
                        : alert.status === 'acknowledged' ? 'text-yellow-400'
                        : 'text-green-400'
                      return (
                        <tr key={alert.id} className="border-b border-border/50 hover:bg-accent/5">
                          <td className="px-2 py-1.5">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${sevColor}`}>
                              {alert.severity}
                            </span>
                          </td>
                          <td className="px-2 py-1.5 text-text2 font-mono">{alert.rule_type}</td>
                          <td className="px-2 py-1.5 text-text2 max-w-[300px] truncate">{alert.summary}</td>
                          <td className="px-2 py-1.5 text-muted">{(alert.confidence * 100).toFixed(0)}%</td>
                          <td className="px-2 py-1.5">
                            <span className={`font-semibold ${statusColor}`}>{alert.status}</span>
                          </td>
                          <td className="px-2 py-1.5">
                            {alert.status === 'new' && (
                              <Button
                                variant="ghost"
                                onClick={async () => {
                                  await reviewAlertApi(alert.id, 'acknowledged', operatorName)
                                  alertsQuery.refetch()
                                  alertSummaryQuery.refetch()
                                }}
                              >
                                {t('investigation.alerts.acknowledge')}
                              </Button>
                            )}
                            {alert.status === 'acknowledged' && (
                              <Button
                                variant="ghost"
                                onClick={async () => {
                                  await reviewAlertApi(alert.id, 'resolved', operatorName)
                                  alertsQuery.refetch()
                                  alertSummaryQuery.refetch()
                                }}
                              >
                                {t('investigation.alerts.resolve')}
                              </Button>
                            )}
                            {alert.status === 'resolved' && (
                              <span className="text-green-400 text-[10px]">{t('investigation.alerts.resolved')}</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : (
            <Card className="p-8 text-center text-muted text-sm">
              {alertsQuery.isLoading ? t('common.loading') : t('investigation.alerts.noAlerts')}
            </Card>
          )}
        </div>
      )}

      {tab === 'cross-account' && (
        <div className="space-y-4">
          {/* Account selector */}
          <Card className="space-y-3">
            <CardTitle>{t('investigation.crossAccount.selectAccount')}</CardTitle>
            <div className="flex gap-3 items-end flex-wrap">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] uppercase text-muted font-semibold">{t('investigation.crossAccount.account')}</label>
                <input
                  value={crossAccountSelected}
                  onChange={e => { setCrossAccountSelected(e.target.value.replace(/\D/g, '')); setCrossAccountTarget('') }}
                  placeholder="1234567890"
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none w-40"
                />
              </div>
              {crossAccountSelected && crossFlowQuery.data && (
                <div className="text-xs text-muted">
                  <span className="text-text font-semibold">{crossFlowQuery.data.name || crossFlowQuery.data.account}</span>
                  {crossFlowQuery.data.bank && <span className="ml-1">({crossFlowQuery.data.bank})</span>}
                </div>
              )}
            </div>
          </Card>

          {/* Flow summary */}
          {crossFlowQuery.data && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Inbound */}
              <Card className="border-green-800/30">
                <CardTitle className="text-green-400 text-sm mb-2">
                  {t('investigation.crossAccount.inbound')} ({crossFlowQuery.data.inbound_count}) — {t('results.flowGraph.totalIn')}: {Number(crossFlowQuery.data.total_in).toLocaleString('th-TH', {minimumFractionDigits: 2})}
                </CardTitle>
                <div className="max-h-60 overflow-y-auto">
                  <table className="w-full text-xs">
                    <tbody>
                      {(crossFlowQuery.data.inbound || []).map((f: any) => (
                        <tr
                          key={f.account}
                          className={`border-b border-border/30 hover:bg-green-900/10 cursor-pointer ${crossAccountTarget === f.account ? 'bg-green-900/20' : ''}`}
                          onClick={() => setCrossAccountTarget(f.account)}
                        >
                          <td className="px-2 py-1 font-mono text-green-400">{f.account}</td>
                          <td className="px-2 py-1 text-text2 truncate max-w-[120px]">{f.name}</td>
                          <td className="px-2 py-1 text-green-400 font-semibold text-right">{Number(f.total).toLocaleString('th-TH')}</td>
                          <td className="px-2 py-1 text-muted text-right">{f.count}x</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              {/* Outbound */}
              <Card className="border-red-800/30">
                <CardTitle className="text-red-400 text-sm mb-2">
                  {t('investigation.crossAccount.outbound')} ({crossFlowQuery.data.outbound_count}) — {t('results.flowGraph.totalOut')}: {Number(crossFlowQuery.data.total_out).toLocaleString('th-TH', {minimumFractionDigits: 2})}
                </CardTitle>
                <div className="max-h-60 overflow-y-auto">
                  <table className="w-full text-xs">
                    <tbody>
                      {(crossFlowQuery.data.outbound || []).map((f: any) => (
                        <tr
                          key={f.account}
                          className={`border-b border-border/30 hover:bg-red-900/10 cursor-pointer ${crossAccountTarget === f.account ? 'bg-red-900/20' : ''}`}
                          onClick={() => setCrossAccountTarget(f.account)}
                        >
                          <td className="px-2 py-1 font-mono text-red-400">{f.account}</td>
                          <td className="px-2 py-1 text-text2 truncate max-w-[120px]">{f.name}</td>
                          <td className="px-2 py-1 text-red-400 font-semibold text-right">{Number(f.total).toLocaleString('th-TH')}</td>
                          <td className="px-2 py-1 text-muted text-right">{f.count}x</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* Pairwise transactions */}
          {crossAccountTarget && crossMatchQuery.data?.items?.length > 0 && (
            <Card>
              <CardTitle className="text-sm mb-2">
                {t('investigation.crossAccount.pairwise')}: {crossAccountSelected} ↔ {crossAccountTarget}
              </CardTitle>
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-surface2">
                    <tr className="border-b border-border text-muted">
                      <th className="px-2 py-1.5 text-left">{t('results.flowGraph.colDate')}</th>
                      <th className="px-2 py-1.5 text-right">{t('results.flowGraph.colAmount')}</th>
                      <th className="px-2 py-1.5 text-left">{t('results.flowGraph.colDir')}</th>
                      <th className="px-2 py-1.5 text-left">{t('results.flowGraph.colType')}</th>
                      <th className="px-2 py-1.5 text-left">{t('results.flowGraph.colDesc')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {crossMatchQuery.data.items.map((txn: any, i: number) => {
                      const isIn = txn.direction === 'IN'
                      return (
                        <tr key={i} className="border-b border-border/50 hover:bg-accent/5">
                          <td className="px-2 py-1 text-text2">{txn.date}</td>
                          <td className={`px-2 py-1 text-right font-mono font-medium ${isIn ? 'text-green-400' : 'text-red-400'}`}>
                            {isIn ? '+' : '-'}{Math.abs(txn.amount).toLocaleString('th-TH', {minimumFractionDigits: 2})}
                          </td>
                          <td className="px-2 py-1">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${isIn ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'}`}>
                              {txn.direction}
                            </span>
                          </td>
                          <td className="px-2 py-1 text-muted">{txn.transaction_type}</td>
                          <td className="px-2 py-1 text-text2 truncate max-w-[200px]">{txn.description}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Path Finder */}
          <Card className="space-y-3">
            <CardTitle className="text-sm">{t('investigation.crossAccount.pathFinder')}</CardTitle>
            <div className="flex gap-3 items-end flex-wrap">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] uppercase text-muted font-semibold">{t('investigation.crossAccount.from')}</label>
                <input
                  value={pathFrom}
                  onChange={e => setPathFrom(e.target.value.replace(/\D/g, ''))}
                  placeholder="1234567890"
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none w-36"
                />
              </div>
              <span className="text-muted text-lg pb-2">→</span>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] uppercase text-muted font-semibold">{t('investigation.crossAccount.to')}</label>
                <input
                  value={pathTo}
                  onChange={e => setPathTo(e.target.value.replace(/\D/g, ''))}
                  placeholder="9876543210"
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none w-36"
                />
              </div>
              <Button
                variant="success"
                onClick={() => pathTraceQuery.refetch()}
                disabled={!pathFrom || !pathTo || pathTraceQuery.isFetching}
              >
                {pathTraceQuery.isFetching ? t('common.loading') : t('investigation.crossAccount.trace')}
              </Button>
            </div>

            {pathTraceQuery.data && (
              <div className="mt-3">
                {pathTraceQuery.data.found ? (
                  <div className="space-y-2">
                    <p className="text-xs text-green-400 font-semibold">
                      {t('investigation.crossAccount.pathsFound')}: {pathTraceQuery.data.path_count}
                    </p>
                    {pathTraceQuery.data.paths.map((path: any, pi: number) => (
                      <div key={pi} className="rounded-lg border border-border bg-surface2/50 p-3">
                        <div className="flex items-center gap-1 flex-wrap text-xs mb-2">
                          {path.hops.map((hop: string, hi: number) => (
                            <span key={hi} className="flex items-center gap-1">
                              <span className="px-2 py-0.5 rounded-full bg-accent/20 text-accent font-mono font-semibold">{hop}</span>
                              {hi < path.hops.length - 1 && <span className="text-red-400">→</span>}
                            </span>
                          ))}
                          <span className="ml-2 text-muted">({path.hop_count} {t('investigation.crossAccount.hops')})</span>
                        </div>
                        <div className="flex gap-3 text-[10px] text-muted">
                          {path.amounts.map((a: any, ai: number) => (
                            <span key={ai}>
                              {a.from.slice(-4)}→{a.to.slice(-4)}: <strong className="text-text">{Number(a.total).toLocaleString('th-TH')}</strong> ({a.count}x)
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted">{t('investigation.crossAccount.noPath')}</p>
                )}
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === 'link-chart' && (
        <LinkChart />
      )}

      {tab === 'timeline' && (
        <div className="space-y-4">
          {timelineAggItems.length > 0 ? (
            <TimelineChart
              transactions={timelineAggItems}
              title={t('investigation.tabs.timeline')}
            />
          ) : (
            <Card className="p-8 text-center text-muted text-sm">
              {timelineAggQuery.isLoading ? t('common.loading') : t('investigation.timelineEmpty')}
            </Card>
          )}
        </div>
      )}

      {tab !== 'database' && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  {tab === 'files' && (
                    <>
                      <th className="py-2 pr-3">File</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 pr-3">Uploaded</th>
                      <th className="py-2 pr-3">Hash</th>
                    </>
                  )}
                  {tab === 'runs' && (
                    <>
                      <th className="py-2 pr-3">Run</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 pr-3">Bank</th>
                      <th className="py-2 pr-3">Started</th>
                    </>
                  )}
                  {tab === 'accounts' && (
                    <>
                      <th className="py-2 pr-3">Bank</th>
                      <th className="py-2 pr-3">Account</th>
                      <th className="py-2 pr-3">Holder</th>
                      <th className="py-2 pr-3">Status</th>
                    </>
                  )}
                  {tab === 'search' && (
                    <>
                      <th className="py-2 pr-3">Datetime</th>
                      <th className="py-2 pr-3">Amount</th>
                      <th className="py-2 pr-3">Type</th>
                      <th className="py-2 pr-3">Counterparty</th>
                      <th className="py-2 pr-3">Review</th>
                    </>
                  )}
                  {tab === 'duplicates' && (
                    <>
                      <th className="py-2 pr-3">Type</th>
                      <th className="py-2 pr-3">Confidence</th>
                      <th className="py-2 pr-3">Reason</th>
                      <th className="py-2 pr-3">Review</th>
                    </>
                  )}
                  {tab === 'matches' && (
                    <>
                      <th className="py-2 pr-3">Match Type</th>
                      <th className="py-2 pr-3">Confidence</th>
                      <th className="py-2 pr-3">Source</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 pr-3">Review</th>
                    </>
                  )}
                  {tab === 'audit' && (
                    <>
                      <th className="py-2 pr-3">Object</th>
                      <th className="py-2 pr-3">Action</th>
                      <th className="py-2 pr-3">Changed By</th>
                      <th className="py-2 pr-3">When</th>
                    </>
                  )}
                  {tab === 'exports' && (
                    <>
                      <th className="py-2 pr-3">Type</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 pr-3">Output</th>
                      <th className="py-2 pr-3">Files</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {currentRows.length === 0 ? (
                  <tr>
                    <td className="py-6 text-sm text-muted" colSpan={5}>No records yet.</td>
                  </tr>
                ) : currentRows.map((row: any) => (
                  <tr key={row.id || row.file_id || row.source_transaction_id || row.object_id} className="border-b border-border/60 align-top">
                    {tab === 'files' && (
                      <>
                        <td className="py-3 pr-3">
                          <button className="text-left" onClick={() => setSelectedFileId(row.id)}>
                            <div className="font-medium text-text hover:text-accent">{row.original_filename}</div>
                            <div className="text-xs text-muted">{row.id}</div>
                          </button>
                        </td>
                        <td className="py-3 pr-3"><Badge variant={String(row.import_status).includes('duplicate') ? 'blue' : 'green'}>{row.import_status}</Badge></td>
                        <td className="py-3 pr-3">{formatValue(row.uploaded_at)}</td>
                        <td className="py-3 pr-3 font-mono text-xs">{compactHash(String(row.file_hash_sha256 || ''))}</td>
                      </>
                    )}
                    {tab === 'runs' && (
                      <>
                        <td className="py-3 pr-3">
                          <button className="font-mono text-xs text-left hover:text-accent" onClick={() => setSelectedRunId(row.id)}>{row.id}</button>
                        </td>
                        <td className="py-3 pr-3"><Badge variant={row.status === 'done' ? 'green' : row.status === 'error' ? 'red' : 'blue'}>{row.status}</Badge></td>
                        <td className="py-3 pr-3">{formatValue(row.bank_detected)}</td>
                        <td className="py-3 pr-3">{formatValue(row.started_at)}</td>
                      </>
                    )}
                    {tab === 'accounts' && (
                      <>
                        <td className="py-3 pr-3">{formatValue(row.bank_name)}</td>
                        <td className="py-3 pr-3">
                          <button className="font-mono text-left hover:text-accent" onClick={() => setSelectedAccountId(row.id)}>
                            {formatValue(row.normalized_account_number)}
                          </button>
                        </td>
                        <td className="py-3 pr-3">{formatValue(row.account_holder_name)}</td>
                        <td className="py-3 pr-3"><Badge variant={row.status === 'active' ? 'green' : 'blue'}>{row.status}</Badge></td>
                      </>
                    )}
                    {tab === 'search' && (
                      <>
                        <td className="py-3 pr-3">
                          <button className="text-left hover:text-accent" onClick={() => setSelectedTransactionId(row.id)}>
                            {formatValue(row.transaction_datetime)}
                          </button>
                        </td>
                        <td className="py-3 pr-3">{typeof row.amount === 'number' ? fmt(row.amount) : formatValue(row.amount)}</td>
                        <td className="py-3 pr-3">{formatValue(row.transaction_type)}</td>
                        <td className="py-3 pr-3">{formatValue(row.counterparty_name_normalized || row.counterparty_account_normalized)}</td>
                        <td className="py-3 pr-3"><Badge variant={row.review_status === 'reviewed' ? 'green' : row.review_status === 'needs_review' ? 'red' : 'blue'}>{row.review_status}</Badge></td>
                      </>
                    )}
                    {tab === 'duplicates' && (
                      <>
                        <td className="py-3 pr-3">{formatValue(row.duplicate_type)}</td>
                        <td className="py-3 pr-3">{formatValue(row.confidence_score)}</td>
                        <td className="py-3 pr-3 max-w-[420px] text-xs text-text2">{formatValue(row.reason)}</td>
                        <td className="py-3 pr-3">
                          <div className="flex gap-2">
                            <Button size="sm" variant="ghost" onClick={() => handleDuplicateReview(row.id, 'confirmed_duplicate')}>Confirm</Button>
                            <Button size="sm" variant="ghost" onClick={() => handleDuplicateReview(row.id, 'rejected')}>Reject</Button>
                          </div>
                        </td>
                      </>
                    )}
                    {tab === 'matches' && (
                      <>
                        <td className="py-3 pr-3">{formatValue(row.match_type)}</td>
                        <td className="py-3 pr-3">{formatValue(row.confidence_score)}</td>
                        <td className="py-3 pr-3 font-mono text-xs">{formatValue(row.source_transaction_id)}</td>
                        <td className="py-3 pr-3"><Badge variant={row.status === 'confirmed' ? 'green' : row.status === 'rejected' ? 'red' : 'blue'}>{row.status}</Badge></td>
                        <td className="py-3 pr-3">
                          <div className="flex gap-2">
                            <Button size="sm" variant="ghost" onClick={() => handleMatchReview(row.id, 'confirmed')}>Confirm</Button>
                            <Button size="sm" variant="ghost" onClick={() => handleMatchReview(row.id, 'rejected')}>Reject</Button>
                          </div>
                        </td>
                      </>
                    )}
                    {tab === 'audit' && (
                      <>
                        <td className="py-3 pr-3">
                          <div className="font-medium text-text">{row.object_type}</div>
                          <div className="font-mono text-xs text-muted">{row.object_id}</div>
                          {row.object_type === 'learning_feedback' && row.extra_context_json?.source_object_type && row.extra_context_json?.source_object_id && (
                            <div className="mt-1 text-xs text-text2">
                              source {row.extra_context_json.source_object_type}:{row.extra_context_json.source_object_id}
                            </div>
                          )}
                        </td>
                        <td className="py-3 pr-3">
                          <div className="text-text">{formatValue(row.action_type)}</div>
                          {row.object_type === 'learning_feedback' && (
                            <div className="mt-1 flex flex-wrap gap-1.5">
                              {row.extra_context_json?.learning_domain && (
                                <Badge variant="blue">{row.extra_context_json.learning_domain}</Badge>
                              )}
                              {row.extra_context_json?.feedback_status && (
                                <Badge variant={auditFeedbackBadgeVariant(row.extra_context_json.feedback_status)}>
                                  {row.extra_context_json.feedback_status === 'corrected'
                                    ? t('investigation.badge.corrected')
                                    : row.extra_context_json.feedback_status === 'confirmed'
                                      ? t('investigation.badge.confirmed')
                                      : t('investigation.badge.unknown')}
                                </Badge>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="py-3 pr-3">{formatValue(row.changed_by)}</td>
                        <td className="py-3 pr-3">{formatValue(row.changed_at)}</td>
                      </>
                    )}
                    {tab === 'exports' && (
                      <>
                        <td className="py-3 pr-3">{formatValue(row.export_type)}</td>
                        <td className="py-3 pr-3"><Badge variant={row.status === 'done' ? 'green' : 'blue'}>{row.status}</Badge></td>
                        <td className="py-3 pr-3 text-xs text-muted">{formatValue(row.output_path)}</td>
                        <td className="py-3 pr-3">
                          <div className="flex flex-col gap-1">
                            {(row.summary_json?.files || []).map((file: string) => (
                              <a
                                key={file}
                                href={`/api/download-export/${row.id}/${encodeURIComponent(file)}?download_name=${encodeURIComponent(file)}`}
                                className="text-accent hover:underline"
                              >
                                {file}
                              </a>
                            ))}
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === 'database' && (
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
                <Button variant="outline" onClick={handleSaveBackupSettings}>Save Schedule</Button>
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
                Current schedule source: <span className="font-mono">{backupSettingsQuery.data?.source || backupsQuery.data?.settings?.source || '—'}</span>{' '}
                · effective format: <span className="font-mono">{backupSettingsQuery.data?.effective_backup_format || '—'}</span>{' '}
                · retention: <span className="font-mono">{backupSettingsQuery.data?.retention_enabled ? `keep ${backupSettingsQuery.data?.retain_count}` : 'off'}</span>
              </div>
              <TextInput
                value={adminNote}
                onChange={(event) => setAdminNote(event.target.value)}
                placeholder="Operation note for backup / reset / restore"
              />
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={handleCreateBackup}>Create Backup</Button>
                <Button variant="ghost" onClick={() => window.location.assign(`/api/download-backup/${encodeURIComponent(selectedBackupFilename)}?download_name=${encodeURIComponent(selectedBackupFilename)}`)} disabled={!selectedBackupFilename}>
                  Download Selected Backup
                </Button>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted">Reset Database</div>
                  <div className="text-xs text-text2">Type: <span className="font-mono">{backupsQuery.data?.reset_confirmation_text || 'RESET BSIE DATABASE'}</span></div>
                  <TextInput
                    value={resetConfirmText}
                    onChange={(event) => setResetConfirmText(event.target.value)}
                    placeholder="Confirmation text"
                  />
                  <Button variant="danger" onClick={handleResetDatabase}>Reset Current Database</Button>
                </div>
                <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted">Restore Backup</div>
                  <div className="text-xs text-text2">Type: <span className="font-mono">{backupsQuery.data?.restore_confirmation_text || 'RESTORE BSIE DATABASE'}</span></div>
                  <TextInput
                    value={restoreConfirmText}
                    onChange={(event) => setRestoreConfirmText(event.target.value)}
                    placeholder="Confirmation text"
                  />
                  <Button variant="success" onClick={handleRestoreDatabase} disabled={!selectedBackupFilename}>Restore Selected Backup</Button>
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
      )}

      {fileDetail && (
        <Card className="space-y-3">
          <CardTitle>File Detail</CardTitle>
          <div className="grid gap-3 lg:grid-cols-2">
            <FieldBlock label="Original Filename" value={fileDetail.original_filename} />
            <FieldBlock label="Stored Path" value={fileDetail.stored_path} mono />
            <FieldBlock label="Hash" value={fileDetail.file_hash_sha256} mono />
            <FieldBlock label="Import Status" value={fileDetail.import_status} />
          </div>
        </Card>
      )}

      {runDetail && (
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <CardTitle>Parser Run Detail</CardTitle>
            <Button variant="outline" onClick={handleReprocess}>Reprocess Run</Button>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <FieldBlock label="Run ID" value={runDetail.id} mono />
            <FieldBlock label="Status" value={runDetail.status} />
            <FieldBlock label="Bank" value={runDetail.bank_detected} />
            <FieldBlock label="Parser Version" value={runDetail.parser_version} />
            <FieldBlock label="Mapping Profile Version" value={runDetail.mapping_profile_version} />
            <FieldBlock label="Summary" value={runDetail.summary_json} />
          </div>
        </Card>
      )}

      {accountDetail && (
        <Card className="space-y-4">
          <CardTitle>Account Detail and Correction</CardTitle>
          <div className="grid gap-3 lg:grid-cols-2">
            <FieldBlock label="Account ID" value={accountDetail.id} mono />
            <FieldBlock label="Normalized Account" value={accountDetail.normalized_account_number} mono />
            <FieldBlock label="Holder" value={accountDetail.account_holder_name} />
            <FieldBlock label="Bank" value={accountDetail.bank_name} />
            <FieldBlock label="Status" value={accountDetail.status} />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <TextInput value={accountEdit.account_holder_name} onChange={(event) => setAccountEdit((state) => ({ ...state, account_holder_name: event.target.value }))} placeholder="New holder name" />
            <TextInput value={accountEdit.bank_name} onChange={(event) => setAccountEdit((state) => ({ ...state, bank_name: event.target.value }))} placeholder="New bank name" />
            <TextInput value={accountEdit.notes} onChange={(event) => setAccountEdit((state) => ({ ...state, notes: event.target.value }))} placeholder="Notes" />
            <TextInput value={accountEdit.reason} onChange={(event) => setAccountEdit((state) => ({ ...state, reason: event.target.value }))} placeholder="Audit reason" />
          </div>
          <div className="flex justify-end">
            <Button variant="success" onClick={handleAccountSave}>Save Account Correction</Button>
          </div>
        </Card>
      )}

      {transactionDetail && (
        <Card className="space-y-4">
          <CardTitle>Transaction Detail and Correction</CardTitle>
          <div className="grid gap-3 lg:grid-cols-2">
            <FieldBlock label="Transaction ID" value={transactionDetail.id} mono />
            <FieldBlock label="Datetime" value={transactionDetail.transaction_datetime} />
            <FieldBlock label="Amount" value={transactionDetail.amount != null ? fmt(transactionDetail.amount) : '—'} />
            <FieldBlock label="Type" value={transactionDetail.transaction_type} />
            <FieldBlock label="Counterparty Account" value={transactionDetail.counterparty_account_normalized} mono />
            <FieldBlock label="Counterparty Name" value={transactionDetail.counterparty_name_normalized} />
            <FieldBlock label="Duplicate Status" value={transactionDetail.duplicate_status} />
            <FieldBlock label="Lineage" value={transactionDetail.lineage_json} />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <TextInput value={transactionEdit.transaction_type} onChange={(event) => setTransactionEdit((state) => ({ ...state, transaction_type: event.target.value }))} placeholder="New transaction type" />
            <TextInput value={transactionEdit.counterparty_name_normalized} onChange={(event) => setTransactionEdit((state) => ({ ...state, counterparty_name_normalized: event.target.value }))} placeholder="New counterparty name" />
            <SelectInput value={transactionEdit.review_status} onChange={(event) => setTransactionEdit((state) => ({ ...state, review_status: event.target.value }))}>
              <option value="">Review status</option>
              <option value="pending">pending</option>
              <option value="needs_review">needs_review</option>
              <option value="reviewed">reviewed</option>
            </SelectInput>
            <TextInput value={transactionEdit.reason} onChange={(event) => setTransactionEdit((state) => ({ ...state, reason: event.target.value }))} placeholder="Audit reason" />
          </div>
          <div className="flex justify-end">
            <Button variant="success" onClick={handleTransactionSave}>Save Transaction Correction</Button>
          </div>
        </Card>
      )}
    </div>
  )
}
