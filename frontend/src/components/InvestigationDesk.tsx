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
import { DatabaseTab } from '@/components/investigation/DatabaseTab'
import { AlertsTab } from '@/components/investigation/AlertsTab'
import { CrossAccountTab } from '@/components/investigation/CrossAccountTab'
import { AiCopilotTab } from '@/components/investigation/AiCopilotTab'

const TAB_IDS = ['database', 'files', 'runs', 'accounts', 'search', 'alerts', 'cross-account', 'link-chart', 'timeline', 'duplicates', 'matches', 'audit', 'exports', 'llm'] as const
const TABLE_TAB_IDS = ['files', 'runs', 'accounts', 'search', 'duplicates', 'matches', 'audit', 'exports'] as const

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
    { id: 'llm' as const, label: t('investigation.tabs.llm') },
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
  const selectedCopilotAccount = String(
    accountDetail?.normalized_account_number
      || accountDetail?.display_account_number
      || crossAccountSelected
      || '',
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
        <AlertsTab
          alertItems={alertItems}
          alertSummary={alertSummary}
          operatorName={operatorName}
          isLoading={alertsQuery.isLoading}
          refetchAlerts={() => alertsQuery.refetch()}
          refetchAlertSummary={() => alertSummaryQuery.refetch()}
        />
      )}

      {tab === 'cross-account' && (
        <CrossAccountTab
          crossAccountSelected={crossAccountSelected}
          setCrossAccountSelected={setCrossAccountSelected}
          crossAccountTarget={crossAccountTarget}
          setCrossAccountTarget={setCrossAccountTarget}
          pathFrom={pathFrom}
          setPathFrom={setPathFrom}
          pathTo={pathTo}
          setPathTo={setPathTo}
          crossFlowData={crossFlowQuery.data}
          crossMatchData={crossMatchQuery.data}
          pathTraceData={pathTraceQuery.data}
          isPathTraceFetching={pathTraceQuery.isFetching}
          refetchPathTrace={() => pathTraceQuery.refetch()}
        />
      )}

      {tab === 'link-chart' && (
        <LinkChart />
      )}

      {tab === 'llm' && (
        <AiCopilotTab
          operatorName={resolvedOperatorName}
          selectedRunId={selectedRunId}
          selectedFileId={selectedFileId}
          selectedAccountNumber={selectedCopilotAccount}
          filterRunId={transactionFilters.parser_run_id}
          filterFileId={transactionFilters.file_id}
          crossAccountNumber={crossAccountSelected}
        />
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

      {(TABLE_TAB_IDS as readonly string[]).includes(tab) && (
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
        <DatabaseTab
          dbStatus={dbStatus}
          backups={backups}
          selectedBackupFilename={selectedBackupFilename}
          setSelectedBackupFilename={setSelectedBackupFilename}
          selectedBackup={selectedBackup}
          backupPreview={backupPreview}
          backupEnabled={backupEnabled}
          setBackupEnabled={setBackupEnabled}
          backupIntervalHours={backupIntervalHours}
          setBackupIntervalHours={setBackupIntervalHours}
          backupRetentionEnabled={backupRetentionEnabled}
          setBackupRetentionEnabled={setBackupRetentionEnabled}
          backupRetainCount={backupRetainCount}
          setBackupRetainCount={setBackupRetainCount}
          adminNote={adminNote}
          setAdminNote={setAdminNote}
          resetConfirmText={resetConfirmText}
          setResetConfirmText={setResetConfirmText}
          restoreConfirmText={restoreConfirmText}
          setRestoreConfirmText={setRestoreConfirmText}
          backupSettingsData={backupSettingsQuery.data}
          backupsData={backupsQuery.data}
          onSaveBackupSettings={handleSaveBackupSettings}
          onCreateBackup={handleCreateBackup}
          onResetDatabase={handleResetDatabase}
          onRestoreDatabase={handleRestoreDatabase}
        />
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
