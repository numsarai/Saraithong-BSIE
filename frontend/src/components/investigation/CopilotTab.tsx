import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BrainCircuit, FileText, History, ListChecks, Loader2, RotateCcw, ScrollText, Send, ShieldAlert, ShieldCheck, Sparkles, Target } from 'lucide-react'
import { askCopilot, getAuditLogs, getCaseTagDetail, listCaseTags, previewClassification, reviewTransaction, searchTransactionRecords, type CaseTagDetail, type CaseTagItem, type CaseTagLinkedObject } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardTitle } from '@/components/ui/card'

type CopilotScope = {
  parser_run_id: string
  file_id: string
  account: string
  case_tag_id: string
  case_tag: string
}

type CopilotTaskMode = 'account_summary' | 'alert_explanation' | 'review_checklist' | 'draft_report_paragraph'

interface CopilotTabProps {
  operatorName: string
  selectedRunId?: string
  selectedFileId?: string
  selectedAccountNumber?: string
  filterRunId?: string
  filterFileId?: string
  crossAccountNumber?: string
}

type ScopedTransactionRow = {
  id?: string | null
  transaction_id?: string | null
  transaction_datetime?: string | null
  posted_date?: string | null
  date?: string | null
  direction?: string | null
  amount?: string | number | null
  description?: string | null
  description_normalized?: string | null
  description_raw?: string | null
  transaction_type?: string | null
  confidence?: string | number | null
  heuristic_confidence?: string | number | null
  parse_confidence?: string | number | null
  channel?: string | null
  counterparty_account?: string | null
  counterparty_account_normalized?: string | null
  counterparty_name?: string | null
  counterparty_name_normalized?: string | null
  reference_no?: string | null
  [key: string]: unknown
}

type ClassificationAuditItem = {
  id?: string | null
  object_id?: string | null
  action_type?: string | null
  field_name?: string | null
  old_value_json?: unknown
  new_value_json?: unknown
  changed_by?: string | null
  changed_at?: string | null
  reason?: string | null
}

const EMPTY_SCOPE: CopilotScope = { parser_run_id: '', file_id: '', account: '', case_tag_id: '', case_tag: '' }
const TASK_MODES: CopilotTaskMode[] = ['account_summary', 'alert_explanation', 'review_checklist', 'draft_report_paragraph']
const TRANSACTION_TYPES = ['IN_TRANSFER', 'OUT_TRANSFER', 'DEPOSIT', 'WITHDRAW', 'FEE', 'SALARY', 'IN_UNKNOWN', 'OUT_UNKNOWN']
const CLASSIFICATION_REVIEW_FIELDS = new Set(['transaction_type', 'counterparty_name_normalized'])
const INITIAL_CLASSIFICATION_PREVIEW = {
  transaction_id: 'TXN-PREVIEW-1',
  date: '',
  direction: 'OUT',
  amount: '',
  description: '',
  transaction_type: 'OUT_TRANSFER',
  confidence: '0.80',
  counterparty_name: '',
}
const TASK_MODE_ICONS = {
  account_summary: FileText,
  alert_explanation: ShieldAlert,
  review_checklist: ListChecks,
  draft_report_paragraph: ScrollText,
} as const

function shortHash(value: string) {
  return value ? `${value.slice(0, 12)}...` : ''
}

function hasScope(scope: CopilotScope) {
  return Boolean(scope.parser_run_id.trim() || scope.file_id.trim() || scope.account.trim() || scope.case_tag_id.trim() || scope.case_tag.trim())
}

function hasClassificationScope(scope: CopilotScope) {
  return Boolean(scope.parser_run_id.trim() || scope.file_id.trim() || scope.account.trim())
}

function normalizeAccount(value: string) {
  return value.replace(/\D/g, '')
}

function textValue(value: unknown) {
  if (value === null || value === undefined) return ''
  return String(value)
}

function numberValue(value: unknown, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function clampLimit(value: string, fallback: number, max: number) {
  const parsed = Number(value || fallback)
  if (!Number.isFinite(parsed)) return fallback
  return Math.max(1, Math.min(max, Math.floor(parsed)))
}

function scopedTransactionKey(row: ScopedTransactionRow, index: number) {
  return textValue(row.transaction_id || row.id || row.reference_no || `preview-row-${index + 1}`)
}

function scopedTransactionDate(row: ScopedTransactionRow) {
  return textValue(row.transaction_datetime || row.posted_date || row.date)
}

function scopedTransactionDescription(row: ScopedTransactionRow) {
  return textValue(row.description || row.description_normalized || row.description_raw)
}

function formatScopedAmount(value: unknown) {
  return numberValue(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function toClassificationPreviewTransaction(row: ScopedTransactionRow, index: number) {
  const description = scopedTransactionDescription(row)
  return {
    transaction_id: scopedTransactionKey(row, index),
    date: scopedTransactionDate(row),
    direction: textValue(row.direction).toUpperCase(),
    amount: numberValue(row.amount),
    description,
    description_normalized: description,
    description_raw: description,
    channel: textValue(row.channel),
    counterparty_account: textValue(row.counterparty_account || row.counterparty_account_normalized),
    counterparty_name: textValue(row.counterparty_name || row.counterparty_name_normalized),
    transaction_type: textValue(row.transaction_type),
    confidence: numberValue(row.confidence ?? row.heuristic_confidence ?? row.parse_confidence),
  }
}

function classificationSuggestionChanges(item: any) {
  const changes: Record<string, string> = {}
  const currentType = textValue(item.current?.transaction_type)
  const suggestedType = textValue(item.suggested?.transaction_type)
  if (suggestedType && suggestedType !== currentType) {
    changes.transaction_type = suggestedType
  }
  const currentName = textValue(item.current?.counterparty_name)
  const suggestedName = textValue(item.suggested?.counterparty_name)
  if (suggestedName && suggestedName !== currentName) {
    changes.counterparty_name_normalized = suggestedName
  }
  return changes
}

function classificationSuggestionCanApply(item: any) {
  return Boolean(item?.would_apply && Object.keys(classificationSuggestionChanges(item)).length > 0)
}

function classificationAuditKey(item: ClassificationAuditItem, index: number) {
  return textValue(item.id || `${item.object_id || 'audit'}-${item.field_name || 'field'}-${item.changed_at || index}`)
}

function isClassificationAuditItem(item: any): item is ClassificationAuditItem {
  return Boolean(
    item
    && item.action_type === 'field_update'
    && CLASSIFICATION_REVIEW_FIELDS.has(textValue(item.field_name))
    && textValue(item.object_id),
  )
}

function formatAuditValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function classificationAuditRevertChanges(item: ClassificationAuditItem) {
  const field = textValue(item.field_name)
  if (!CLASSIFICATION_REVIEW_FIELDS.has(field)) return {}
  return { [field]: item.old_value_json ?? '' }
}

function caseTagCountLabel(tag: CaseTagItem, linkedLabel: string) {
  const counts = Object.entries(tag.linked_object_counts || {})
    .filter(([, count]) => Number(count) > 0)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([type, count]) => `${type} ${count}`)
  return counts.length ? `${linkedLabel} · ${counts.join(' · ')}` : linkedLabel
}

export function CopilotTab({
  operatorName,
  selectedRunId = '',
  selectedFileId = '',
  selectedAccountNumber = '',
  filterRunId = '',
  filterFileId = '',
  crossAccountNumber = '',
}: CopilotTabProps) {
  const { t } = useTranslation()
  const [scope, setScope] = useState<CopilotScope>(EMPTY_SCOPE)
  const [taskMode, setTaskMode] = useState<CopilotTaskMode>('account_summary')
  const [question, setQuestion] = useState('')
  const [maxTransactions, setMaxTransactions] = useState('20')
  const [isAsking, setIsAsking] = useState(false)
  const [caseTags, setCaseTags] = useState<CaseTagItem[]>([])
  const [caseTagQuery, setCaseTagQuery] = useState('')
  const [isLoadingCaseTags, setIsLoadingCaseTags] = useState(false)
  const [caseTagError, setCaseTagError] = useState('')
  const [caseTagDetail, setCaseTagDetail] = useState<CaseTagDetail | null>(null)
  const [isLoadingCaseTagDetail, setIsLoadingCaseTagDetail] = useState(false)
  const [caseTagDetailError, setCaseTagDetailError] = useState('')
  const [answer, setAnswer] = useState<any>(null)
  const [error, setError] = useState('')
  const [classificationForm, setClassificationForm] = useState(INITIAL_CLASSIFICATION_PREVIEW)
  const [classificationPreview, setClassificationPreview] = useState<any>(null)
  const [classificationPreviewError, setClassificationPreviewError] = useState('')
  const [isPreviewingClassification, setIsPreviewingClassification] = useState(false)
  const [scopedClassificationRows, setScopedClassificationRows] = useState<ScopedTransactionRow[]>([])
  const [selectedScopedClassificationKeys, setSelectedScopedClassificationKeys] = useState<string[]>([])
  const [hasLoadedScopedClassificationRows, setHasLoadedScopedClassificationRows] = useState(false)
  const [isLoadingScopedClassificationRows, setIsLoadingScopedClassificationRows] = useState(false)
  const [selectedClassificationSuggestionIds, setSelectedClassificationSuggestionIds] = useState<string[]>([])
  const [classificationApplyReason, setClassificationApplyReason] = useState('')
  const [classificationApplyError, setClassificationApplyError] = useState('')
  const [classificationApplyResult, setClassificationApplyResult] = useState<any>(null)
  const [classificationAppliedHistory, setClassificationAppliedHistory] = useState<Array<{ transaction_id: string; changes: Record<string, string>; reason: string }>>([])
  const [isApplyingClassificationSuggestions, setIsApplyingClassificationSuggestions] = useState(false)
  const [classificationAuditHistory, setClassificationAuditHistory] = useState<ClassificationAuditItem[]>([])
  const [classificationAuditError, setClassificationAuditError] = useState('')
  const [isLoadingClassificationAuditHistory, setIsLoadingClassificationAuditHistory] = useState(false)
  const [classificationRevertReason, setClassificationRevertReason] = useState('')
  const [classificationRevertError, setClassificationRevertError] = useState('')
  const [classificationRevertResult, setClassificationRevertResult] = useState<any>(null)
  const [revertingClassificationAuditKey, setRevertingClassificationAuditKey] = useState('')

  useEffect(() => {
    let cancelled = false
    setIsLoadingCaseTags(true)
    setCaseTagError('')
    listCaseTags()
      .then((payload) => {
        if (!cancelled) setCaseTags(Array.isArray(payload.items) ? payload.items : [])
      })
      .catch((err: any) => {
        if (!cancelled) setCaseTagError(err.message || String(err))
      })
      .finally(() => {
        if (!cancelled) setIsLoadingCaseTags(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const quickScopes = useMemo(() => [
    {
      key: 'selectedRun',
      label: t('investigation.copilot.scopeSelectedRun'),
      disabled: !selectedRunId,
      value: { parser_run_id: selectedRunId },
    },
    {
      key: 'selectedFile',
      label: t('investigation.copilot.scopeSelectedFile'),
      disabled: !selectedFileId,
      value: { file_id: selectedFileId },
    },
    {
      key: 'selectedAccount',
      label: t('investigation.copilot.scopeSelectedAccount'),
      disabled: !selectedAccountNumber,
      value: { account: normalizeAccount(selectedAccountNumber) },
    },
    {
      key: 'transactionFilters',
      label: t('investigation.copilot.scopeTransactionFilters'),
      disabled: !(filterRunId || filterFileId),
      value: { parser_run_id: filterRunId, file_id: filterFileId },
    },
    {
      key: 'crossAccount',
      label: t('investigation.copilot.scopeCrossAccount'),
      disabled: !crossAccountNumber,
      value: { account: normalizeAccount(crossAccountNumber) },
    },
  ], [crossAccountNumber, filterFileId, filterRunId, selectedAccountNumber, selectedFileId, selectedRunId, t])

  const selectedCaseTagId = caseTags.some((tag) => tag.id === scope.case_tag_id) ? scope.case_tag_id : ''
  const selectedCaseTag = caseTags.find((tag) => tag.id === selectedCaseTagId)
  const filteredCaseTags = useMemo(() => {
    const query = caseTagQuery.trim().toLowerCase()
    if (!query) return caseTags
    return caseTags.filter((tag) => {
      const searchable = [
        tag.tag,
        tag.description || '',
        ...Object.keys(tag.linked_object_counts || {}),
      ].join(' ').toLowerCase()
      return searchable.includes(query)
    })
  }, [caseTagQuery, caseTags])
  const caseTagsForPicker = useMemo(() => {
    if (!selectedCaseTag || filteredCaseTags.some((tag) => tag.id === selectedCaseTag.id)) {
      return filteredCaseTags
    }
    return [selectedCaseTag, ...filteredCaseTags]
  }, [filteredCaseTags, selectedCaseTag])
  const scopedClassificationLimit = clampLimit(maxTransactions, 10, 25)
  const allScopedClassificationRowsSelected = scopedClassificationRows.length > 0 && selectedScopedClassificationKeys.length === scopedClassificationRows.length

  useEffect(() => {
    if (!selectedCaseTagId) {
      setCaseTagDetail(null)
      setCaseTagDetailError('')
      return
    }
    let cancelled = false
    setIsLoadingCaseTagDetail(true)
    setCaseTagDetailError('')
    getCaseTagDetail(selectedCaseTagId)
      .then((payload) => {
        if (!cancelled) setCaseTagDetail(payload)
      })
      .catch((err: any) => {
        if (!cancelled) setCaseTagDetailError(err.message || String(err))
      })
      .finally(() => {
        if (!cancelled) setIsLoadingCaseTagDetail(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedCaseTagId])

  useEffect(() => {
    setScopedClassificationRows([])
    setSelectedScopedClassificationKeys([])
    setHasLoadedScopedClassificationRows(false)
    setClassificationAppliedHistory([])
    setClassificationAuditHistory([])
    setClassificationRevertReason('')
  }, [scope.account, scope.file_id, scope.parser_run_id])

  useEffect(() => {
    setSelectedClassificationSuggestionIds([])
    setClassificationApplyError('')
    setClassificationApplyResult(null)
  }, [classificationPreview])

  const selectCaseTag = (caseTagId: string) => {
    const tag = caseTags.find((item) => item.id === caseTagId)
    setScope((state) => ({
      ...state,
      case_tag_id: tag?.id || '',
      case_tag: tag?.tag || '',
    }))
  }

  const focusLinkedScope = (linked: CaseTagLinkedObject) => {
    setScope((state) => ({
      ...state,
      parser_run_id: linked.scope?.parser_run_id ?? state.parser_run_id,
      file_id: linked.scope?.file_id ?? state.file_id,
      account: linked.scope?.account ?? state.account,
    }))
  }

  const submit = async () => {
    if (!hasScope(scope)) return
    setIsAsking(true)
    setError('')
    try {
      const payload = await askCopilot({
        question: question.trim(),
        task_mode: taskMode,
        scope,
        operator: operatorName,
        max_transactions: clampLimit(maxTransactions, 20, 50),
      })
      setAnswer(payload)
    } catch (err: any) {
      setError(err.message || String(err))
    } finally {
      setIsAsking(false)
    }
  }

  const submitClassificationPreview = async () => {
    setIsPreviewingClassification(true)
    setClassificationPreviewError('')
    try {
      const payload = await previewClassification({
        transactions: [
          {
            transaction_id: classificationForm.transaction_id.trim() || 'TXN-PREVIEW-1',
            date: classificationForm.date.trim(),
            direction: classificationForm.direction,
            amount: Number(classificationForm.amount || 0),
            description_raw: classificationForm.description.trim(),
            transaction_type: classificationForm.transaction_type,
            confidence: Number(classificationForm.confidence || 0),
            counterparty_name: classificationForm.counterparty_name.trim(),
          },
        ],
      })
      setClassificationPreview(payload)
    } catch (err: any) {
      setClassificationPreviewError(err.message || String(err))
    } finally {
      setIsPreviewingClassification(false)
    }
  }

  const refreshScopedClassificationRows = async ({
    resetPreview = false,
    resetHistory = false,
  }: { resetPreview?: boolean; resetHistory?: boolean } = {}) => {
    if (!hasClassificationScope(scope)) return
    setIsLoadingScopedClassificationRows(true)
    setClassificationPreviewError('')
    if (resetPreview) setHasLoadedScopedClassificationRows(false)
    try {
      const payload = await searchTransactionRecords({
        parser_run_id: scope.parser_run_id.trim(),
        file_id: scope.file_id.trim(),
        account: normalizeAccount(scope.account) || scope.account.trim(),
        limit: scopedClassificationLimit,
        offset: 0,
      })
      const rows = Array.isArray(payload.items) ? payload.items as ScopedTransactionRow[] : []
      setScopedClassificationRows(rows)
      setSelectedScopedClassificationKeys([])
      setHasLoadedScopedClassificationRows(true)
      if (resetPreview) setClassificationPreview(null)
      if (resetHistory) setClassificationAppliedHistory([])
    } catch (err: any) {
      setClassificationPreviewError(err.message || String(err))
    } finally {
      setIsLoadingScopedClassificationRows(false)
    }
  }

  const loadScopedClassificationRows = async () => {
    await refreshScopedClassificationRows({ resetPreview: true, resetHistory: true })
  }

  const toggleScopedClassificationRow = (row: ScopedTransactionRow, index: number) => {
    const key = scopedTransactionKey(row, index)
    setSelectedScopedClassificationKeys((state) => (
      state.includes(key) ? state.filter((item) => item !== key) : [...state, key]
    ))
  }

  const toggleAllScopedClassificationRows = () => {
    setSelectedScopedClassificationKeys(allScopedClassificationRowsSelected
      ? []
      : scopedClassificationRows.map((row, index) => scopedTransactionKey(row, index)))
  }

  const submitSelectedClassificationPreview = async () => {
    const selectedRows = scopedClassificationRows
      .map((row, index) => ({ row, index, key: scopedTransactionKey(row, index) }))
      .filter((item) => selectedScopedClassificationKeys.includes(item.key))
    if (!selectedRows.length) return
    setIsPreviewingClassification(true)
    setClassificationPreviewError('')
    try {
      const payload = await previewClassification({
        transactions: selectedRows.map((item) => toClassificationPreviewTransaction(item.row, item.index)),
      })
      setClassificationPreview({ ...payload, preview_input: 'selected' })
    } catch (err: any) {
      setClassificationPreviewError(err.message || String(err))
    } finally {
      setIsPreviewingClassification(false)
    }
  }

  const previewItems = Array.isArray(classificationPreview?.items) ? classificationPreview.items.slice(0, 10) : []
  const canApplyClassificationPreview = classificationPreview?.preview_input === 'selected'
  const applicablePreviewItems = previewItems.filter(classificationSuggestionCanApply)
  const selectedApplicablePreviewItems = applicablePreviewItems.filter((item: any) => selectedClassificationSuggestionIds.includes(item.transaction_id))

  const toggleClassificationSuggestion = (transactionId: string) => {
    setSelectedClassificationSuggestionIds((state) => (
      state.includes(transactionId) ? state.filter((item) => item !== transactionId) : [...state, transactionId]
    ))
  }

  const loadClassificationAuditHistory = async () => {
    const transactionIds = Array.from(new Set(
      scopedClassificationRows.map((row, index) => scopedTransactionKey(row, index)).filter(Boolean),
    )).slice(0, 25)
    if (!transactionIds.length) return
    setIsLoadingClassificationAuditHistory(true)
    setClassificationAuditError('')
    setClassificationRevertError('')
    try {
      const payloads = await Promise.all(
        transactionIds.map((transactionId) => getAuditLogs({
          object_type: 'transaction',
          object_id: transactionId,
          limit: 20,
        })),
      )
      const items = payloads
        .flatMap((payload) => (Array.isArray(payload.items) ? payload.items : []))
        .filter(isClassificationAuditItem)
        .sort((left, right) => textValue(right.changed_at).localeCompare(textValue(left.changed_at)))
      setClassificationAuditHistory(items)
    } catch (err: any) {
      setClassificationAuditError(err.message || String(err))
    } finally {
      setIsLoadingClassificationAuditHistory(false)
    }
  }

  const revertClassificationAuditChange = async (item: ClassificationAuditItem, index: number) => {
    const reason = classificationRevertReason.trim()
    const transactionId = textValue(item.object_id)
    const changes = classificationAuditRevertChanges(item)
    if (!reason || !transactionId || Object.keys(changes).length === 0) return
    const auditKey = classificationAuditKey(item, index)
    setRevertingClassificationAuditKey(auditKey)
    setClassificationRevertError('')
    setClassificationRevertResult(null)
    try {
      await reviewTransaction(transactionId, {
        reviewer: operatorName || 'analyst',
        reason,
        changes,
      })
      setClassificationRevertResult({ status: 'ok', transaction_id: transactionId, field_name: item.field_name })
      await refreshScopedClassificationRows({ resetPreview: false })
      await loadClassificationAuditHistory()
    } catch (err: any) {
      setClassificationRevertError(err.message || String(err))
    } finally {
      setRevertingClassificationAuditKey('')
    }
  }

  const applySelectedClassificationSuggestions = async () => {
    const reason = classificationApplyReason.trim()
    if (!selectedApplicablePreviewItems.length || !reason) return
    setIsApplyingClassificationSuggestions(true)
    setClassificationApplyError('')
    setClassificationApplyResult(null)
    try {
      const applied: Array<{ transaction_id: string; changes: Record<string, string>; reason: string }> = []
      for (const item of selectedApplicablePreviewItems) {
        const changes = classificationSuggestionChanges(item)
        await reviewTransaction(item.transaction_id, {
          reviewer: operatorName || 'analyst',
          reason,
          changes,
        })
        applied.push({ transaction_id: item.transaction_id, changes, reason })
      }
      setClassificationApplyResult({ status: 'ok', applied_count: applied.length, transaction_ids: applied.map((item) => item.transaction_id) })
      setClassificationAppliedHistory((state) => [...applied, ...state].slice(0, 10))
      setSelectedClassificationSuggestionIds([])
      await refreshScopedClassificationRows({ resetPreview: false })
      if (classificationAuditHistory.length > 0) {
        await loadClassificationAuditHistory()
      }
    } catch (err: any) {
      setClassificationApplyError(err.message || String(err))
    } finally {
      setIsApplyingClassificationSuggestions(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <CardTitle className="mb-0">
            <BrainCircuit size={18} />
            {t('investigation.copilot.title')}
          </CardTitle>
          <div className="flex flex-wrap gap-2">
            <Badge variant="green">{t('investigation.copilot.readOnly')}</Badge>
            <Badge variant="blue">{t('investigation.copilot.citationRequired')}</Badge>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.parserRunId')}
            <input
              value={scope.parser_run_id}
              onChange={(event) => setScope((state) => ({ ...state, parser_run_id: event.target.value.trim() }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 font-mono text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.fileId')}
            <input
              value={scope.file_id}
              onChange={(event) => setScope((state) => ({ ...state, file_id: event.target.value.trim() }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 font-mono text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.account')}
            <input
              value={scope.account}
              onChange={(event) => setScope((state) => ({ ...state, account: normalizeAccount(event.target.value) }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 font-mono text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.caseTagFilter')}
            <input
              value={caseTagQuery}
              onChange={(event) => setCaseTagQuery(event.target.value)}
              placeholder={t('investigation.copilot.caseTagFilterPlaceholder')}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.caseTagPicker')}
            <select
              value={selectedCaseTagId}
              onChange={(event) => selectCaseTag(event.target.value)}
              disabled={isLoadingCaseTags}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="">
                {isLoadingCaseTags ? t('investigation.copilot.caseTagLoading') : t('investigation.copilot.caseTagSelect', { count: filteredCaseTags.length })}
              </option>
              {caseTagsForPicker.map((tag) => (
                <option key={tag.id} value={tag.id}>
                  {tag.tag}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.caseTagId')}
            <input
              value={scope.case_tag_id}
              onChange={(event) => setScope((state) => ({ ...state, case_tag_id: event.target.value.trim(), case_tag: '' }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 font-mono text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.caseTag')}
            <input
              value={scope.case_tag}
              onChange={(event) => setScope((state) => ({ ...state, case_tag_id: '', case_tag: event.target.value.trim() }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 font-mono text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
        </div>
        {caseTagError && (
          <div className="text-xs text-danger">
            {t('investigation.copilot.caseTagLoadFailed')}
          </div>
        )}
        {selectedCaseTag && (
          <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
            <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
              <div className="font-mono text-sm font-semibold text-text">{selectedCaseTag.tag}</div>
              <div className="text-xs text-muted">
                {caseTagCountLabel(
                  selectedCaseTag,
                  t('investigation.copilot.caseTagLinkedTotal', { count: Number(selectedCaseTag.linked_object_count || 0) }),
                )}
              </div>
            </div>
            {selectedCaseTag.description && (
              <div className="mt-1 text-sm text-muted">{selectedCaseTag.description}</div>
            )}
            <div className="mt-3 border-t border-border pt-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                {t('investigation.copilot.caseTagLinkedObjects')}
              </div>
              {isLoadingCaseTagDetail && (
                <div className="flex items-center gap-2 text-sm text-muted">
                  <Loader2 size={14} className="animate-spin" />
                  {t('investigation.copilot.caseTagDetailLoading')}
                </div>
              )}
              {caseTagDetailError && (
                <div className="text-sm text-danger">
                  {t('investigation.copilot.caseTagDetailFailed')}
                </div>
              )}
              {!isLoadingCaseTagDetail && !caseTagDetailError && caseTagDetail && (
                <div className="max-h-64 overflow-y-auto rounded-md border border-border bg-surface">
                  {caseTagDetail.links.length === 0 ? (
                    <div className="px-3 py-2 text-sm text-muted">{t('investigation.copilot.caseTagNoLinks')}</div>
                  ) : (
                    <div className="divide-y divide-border">
                      {caseTagDetail.links.map((linked) => {
                        const canFocus = Boolean(linked.scope?.parser_run_id || linked.scope?.file_id || linked.scope?.account)
                        return (
                          <div key={linked.link_id} className="flex flex-col gap-2 px-3 py-2 md:flex-row md:items-start md:justify-between">
                            <div className="min-w-0 space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge>{linked.object_type}</Badge>
                                <span className="font-mono text-xs text-muted">{linked.citation_id || linked.object_id}</span>
                                {linked.found === false && <Badge variant="yellow">{t('investigation.copilot.caseTagMissingObject')}</Badge>}
                              </div>
                              <div className="text-sm font-semibold text-text">{linked.label || linked.object_id}</div>
                              {linked.summary && <div className="text-sm text-muted">{linked.summary}</div>}
                            </div>
                            {canFocus && (
                              <Button size="sm" variant="ghost" onClick={() => focusLinkedScope(linked)}>
                                <Target size={14} />
                                {t('investigation.copilot.caseTagFocusScope')}
                              </Button>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {quickScopes.map((item) => (
            <Button
              key={item.key}
              size="sm"
              variant="ghost"
              disabled={item.disabled}
              onClick={() => setScope((state) => ({ ...state, ...item.value }))}
            >
              {item.label}
            </Button>
          ))}
          <Button size="sm" variant="outline" onClick={() => setScope(EMPTY_SCOPE)}>
            {t('investigation.copilot.clearScope')}
          </Button>
        </div>
      </Card>

      <Card className="space-y-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <CardTitle className="mb-0">
            <Sparkles size={18} />
            {t('investigation.copilot.classificationPreview')}
          </CardTitle>
          <div className="flex flex-wrap gap-2">
            <Badge variant="green">{t('investigation.copilot.readOnly')}</Badge>
            <Badge variant="blue">{t('investigation.copilot.localOnly')}</Badge>
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.previewTxnId')}
            <input
              value={classificationForm.transaction_id}
              onChange={(event) => setClassificationForm((state) => ({ ...state, transaction_id: event.target.value }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 font-mono text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.previewDate')}
            <input
              type="date"
              value={classificationForm.date}
              onChange={(event) => setClassificationForm((state) => ({ ...state, date: event.target.value }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.previewDirection')}
            <select
              value={classificationForm.direction}
              onChange={(event) => setClassificationForm((state) => ({ ...state, direction: event.target.value }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            >
              <option value="OUT">OUT</option>
              <option value="IN">IN</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.previewAmount')}
            <input
              type="number"
              value={classificationForm.amount}
              onChange={(event) => setClassificationForm((state) => ({ ...state, amount: event.target.value }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted xl:col-span-2">
            {t('investigation.copilot.previewDescription')}
            <textarea
              value={classificationForm.description}
              onChange={(event) => setClassificationForm((state) => ({ ...state, description: event.target.value }))}
              rows={3}
              className="min-h-[92px] resize-y rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.previewCurrentType')}
            <select
              value={classificationForm.transaction_type}
              onChange={(event) => setClassificationForm((state) => ({ ...state, transaction_type: event.target.value }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            >
              {TRANSACTION_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.previewConfidence')}
            <input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={classificationForm.confidence}
              onChange={(event) => setClassificationForm((state) => ({ ...state, confidence: event.target.value }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted xl:col-span-2">
            {t('investigation.copilot.previewCounterparty')}
            <input
              value={classificationForm.counterparty_name}
              onChange={(event) => setClassificationForm((state) => ({ ...state, counterparty_name: event.target.value }))}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <div className="flex flex-col justify-end gap-2">
            <Button onClick={submitClassificationPreview} disabled={isPreviewingClassification || !classificationForm.description.trim()}>
              {isPreviewingClassification ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {isPreviewingClassification ? t('investigation.copilot.previewingClassification') : t('investigation.copilot.previewClassificationAction')}
            </Button>
            <Button variant="outline" onClick={loadScopedClassificationRows} disabled={isLoadingScopedClassificationRows || !hasClassificationScope(scope)}>
              {isLoadingScopedClassificationRows ? <Loader2 size={16} className="animate-spin" /> : <Target size={16} />}
              {isLoadingScopedClassificationRows ? t('investigation.copilot.loadingScopedTransactions') : t('investigation.copilot.loadScopedTransactions')}
            </Button>
          </div>
        </div>
        {hasLoadedScopedClassificationRows && (
          <div className="space-y-3 rounded-lg border border-border bg-surface2 p-3">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-sm font-semibold text-text">{t('investigation.copilot.scopedTransactionPicker')}</div>
                <div className="text-xs text-muted">
                  {t('investigation.copilot.scopedTransactionsLoaded', {
                    count: scopedClassificationRows.length,
                    selected: selectedScopedClassificationKeys.length,
                  })}
                </div>
              </div>
              <Button
                size="sm"
                onClick={submitSelectedClassificationPreview}
                disabled={isPreviewingClassification || selectedScopedClassificationKeys.length === 0}
              >
                {isPreviewingClassification ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                {t('investigation.copilot.previewSelectedClassification')}
              </Button>
            </div>
            {scopedClassificationRows.length === 0 ? (
              <div className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-muted">
                {t('investigation.copilot.noScopedTransactions')}
              </div>
            ) : (
              <div className="max-h-72 overflow-auto rounded-md border border-border bg-surface">
                <table className="min-w-full table-fixed text-left text-xs">
                  <thead className="sticky top-0 bg-surface2 text-[11px] font-semibold uppercase tracking-wide text-muted">
                    <tr>
                      <th className="w-10 px-3 py-2">
                        <input
                          type="checkbox"
                          aria-label={t('investigation.copilot.selectAllScopedTransactions')}
                          checked={allScopedClassificationRowsSelected}
                          onChange={toggleAllScopedClassificationRows}
                          className="h-4 w-4 rounded border-border bg-surface"
                        />
                      </th>
                      <th className="w-44 px-3 py-2">{t('investigation.copilot.scopedTransactionId')}</th>
                      <th className="w-32 px-3 py-2">{t('investigation.copilot.scopedTransactionDate')}</th>
                      <th className="w-24 px-3 py-2">{t('investigation.copilot.scopedTransactionDirection')}</th>
                      <th className="w-32 px-3 py-2 text-right">{t('investigation.copilot.scopedTransactionAmount')}</th>
                      <th className="w-40 px-3 py-2">{t('investigation.copilot.scopedTransactionType')}</th>
                      <th className="min-w-[16rem] px-3 py-2">{t('investigation.copilot.scopedTransactionDescription')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {scopedClassificationRows.map((row, index) => {
                      const rowKey = scopedTransactionKey(row, index)
                      const checked = selectedScopedClassificationKeys.includes(rowKey)
                      return (
                        <tr key={rowKey} className={checked ? 'bg-accent/10' : undefined}>
                          <td className="px-3 py-2 align-top">
                            <input
                              type="checkbox"
                              aria-label={t('investigation.copilot.selectScopedTransaction', { id: rowKey })}
                              checked={checked}
                              onChange={() => toggleScopedClassificationRow(row, index)}
                              className="h-4 w-4 rounded border-border bg-surface"
                            />
                          </td>
                          <td className="px-3 py-2 align-top font-mono text-text">{rowKey}</td>
                          <td className="px-3 py-2 align-top text-muted">{scopedTransactionDate(row).slice(0, 10) || '—'}</td>
                          <td className="px-3 py-2 align-top font-mono text-text">{textValue(row.direction) || '—'}</td>
                          <td className="px-3 py-2 align-top text-right font-mono text-text">{formatScopedAmount(row.amount)}</td>
                          <td className="px-3 py-2 align-top font-mono text-text">{textValue(row.transaction_type) || '—'}</td>
                          <td className="px-3 py-2 align-top text-text">
                            <div className="max-w-[28rem] whitespace-normal break-words">
                              {scopedTransactionDescription(row) || '—'}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {classificationAppliedHistory.length > 0 && (
              <div className="space-y-2 rounded-md border border-border bg-surface p-3">
                <div className="text-sm font-semibold text-text">{t('investigation.copilot.classificationAppliedHistory')}</div>
                <div className="space-y-2">
                  {classificationAppliedHistory.map((item, index) => (
                    <div key={`${item.transaction_id}-${index}`} className="rounded-md border border-border bg-surface2 px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="green">{item.transaction_id}</Badge>
                        <span className="font-mono text-xs text-text">
                          {Object.entries(item.changes).map(([field, value]) => `${field}: ${value}`).join(' · ')}
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-muted">
                        {t('investigation.copilot.classificationAppliedReason', { reason: item.reason })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="space-y-3 rounded-md border border-border bg-surface p-3">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div className="text-sm font-semibold text-text">{t('investigation.copilot.classificationAuditHistory')}</div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={loadClassificationAuditHistory}
                  disabled={isLoadingClassificationAuditHistory || scopedClassificationRows.length === 0}
                >
                  {isLoadingClassificationAuditHistory ? <Loader2 size={14} className="animate-spin" /> : <History size={14} />}
                  {isLoadingClassificationAuditHistory
                    ? t('investigation.copilot.loadingClassificationAuditHistory')
                    : t('investigation.copilot.loadClassificationAuditHistory')}
                </Button>
              </div>
              {classificationAuditError && (
                <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                  {classificationAuditError}
                </div>
              )}
              {classificationAuditHistory.length === 0 && !isLoadingClassificationAuditHistory ? (
                <div className="rounded-md border border-border bg-surface2 px-3 py-2 text-sm text-muted">
                  {t('investigation.copilot.classificationAuditEmpty')}
                </div>
              ) : (
                classificationAuditHistory.length > 0 && (
                  <div className="space-y-3">
                    <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
                      {t('investigation.copilot.classificationRevertReason')}
                      <input
                        value={classificationRevertReason}
                        onChange={(event) => setClassificationRevertReason(event.target.value)}
                        placeholder={t('investigation.copilot.classificationRevertReasonPlaceholder')}
                        className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
                      />
                    </label>
                    <div className="space-y-2">
                      {classificationAuditHistory.map((item, index) => {
                        const auditKey = classificationAuditKey(item, index)
                        return (
                          <div key={auditKey} className="rounded-md border border-border bg-surface2 px-3 py-2">
                            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                              <div className="min-w-0 space-y-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge variant="blue">{item.object_id || '—'}</Badge>
                                  <span className="font-mono text-xs text-text">{item.field_name || '—'}</span>
                                  <span className="font-mono text-xs text-muted">
                                    {formatAuditValue(item.old_value_json)} -&gt; {formatAuditValue(item.new_value_json)}
                                  </span>
                                </div>
                                <div className="text-xs text-muted">
                                  {t('investigation.copilot.classificationAuditMeta', {
                                    reviewer: item.changed_by || 'analyst',
                                    date: textValue(item.changed_at).slice(0, 10) || '—',
                                  })}
                                </div>
                                {item.reason && (
                                  <div className="text-xs text-muted">
                                    {t('investigation.copilot.classificationAppliedReason', { reason: item.reason })}
                                  </div>
                                )}
                              </div>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => revertClassificationAuditChange(item, index)}
                                disabled={revertingClassificationAuditKey === auditKey || !classificationRevertReason.trim()}
                              >
                                {revertingClassificationAuditKey === auditKey ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                                {revertingClassificationAuditKey === auditKey
                                  ? t('investigation.copilot.revertingClassificationChange')
                                  : t('investigation.copilot.revertClassificationChange')}
                              </Button>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              )}
              {classificationRevertError && (
                <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                  {classificationRevertError}
                </div>
              )}
              {classificationRevertResult && (
                <div className="rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
                  {t('investigation.copilot.classificationRevertDone', {
                    id: classificationRevertResult.transaction_id,
                    field: classificationRevertResult.field_name,
                  })}
                </div>
              )}
            </div>
          </div>
        )}
        {classificationPreviewError && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {classificationPreviewError}
          </div>
        )}
        {classificationPreview && (
          <div className="flex flex-wrap gap-2 text-xs text-muted">
            <Badge variant={classificationPreview.status === 'ok' ? 'green' : 'yellow'}>{classificationPreview.status}</Badge>
            <Badge variant="blue">{classificationPreview.preview_input || 'manual'}</Badge>
            <span>{t('investigation.copilot.previewSummary', {
              total: Number(classificationPreview.total || 0),
              suggestions: Number(classificationPreview.suggestion_count || 0),
              review: Number(classificationPreview.review_count || 0),
            })}</span>
          </div>
        )}
        {previewItems.length > 0 && (
          <div className="space-y-3 rounded-lg border border-border bg-surface2 p-3">
            {previewItems.map((previewItem: any) => (
              <div key={previewItem.transaction_id} className="space-y-3 border-b border-border pb-3 last:border-b-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  {canApplyClassificationPreview && classificationSuggestionCanApply(previewItem) && (
                    <label className="flex items-center gap-2 rounded-md border border-border bg-surface px-2 py-1 text-xs font-semibold text-text">
                      <input
                        type="checkbox"
                        aria-label={t('investigation.copilot.selectClassificationSuggestion', { id: previewItem.transaction_id })}
                        checked={selectedClassificationSuggestionIds.includes(previewItem.transaction_id)}
                        onChange={() => toggleClassificationSuggestion(previewItem.transaction_id)}
                        className="h-4 w-4 rounded border-border bg-surface"
                      />
                      {t('investigation.copilot.classificationSuggestionApplyCandidate')}
                    </label>
                  )}
                  <Badge variant={previewItem.review_required ? 'yellow' : 'green'}>{previewItem.action}</Badge>
                  <Badge variant="blue">{classificationPreview.model || 'local'}</Badge>
                  <span className="font-mono text-xs text-muted">{previewItem.transaction_id}</span>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-md border border-border bg-surface px-3 py-2">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('investigation.copilot.previewCurrent')}</div>
                    <div className="font-mono text-sm text-text">{previewItem.current?.transaction_type || '—'}</div>
                    <div className="text-xs text-muted">{Number(previewItem.current?.confidence || 0).toFixed(2)}</div>
                    {previewItem.current?.counterparty_name && <div className="text-xs text-muted">{previewItem.current.counterparty_name}</div>}
                  </div>
                  <div className="rounded-md border border-border bg-surface px-3 py-2">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('investigation.copilot.previewAi')}</div>
                    <div className="font-mono text-sm text-text">{previewItem.ai?.transaction_type || '—'}</div>
                    <div className="text-xs text-muted">{Number(previewItem.ai?.confidence || 0).toFixed(2)}</div>
                    {previewItem.ai?.counterparty_name && <div className="text-xs text-muted">{previewItem.ai.counterparty_name}</div>}
                  </div>
                  <div className="rounded-md border border-border bg-surface px-3 py-2">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('investigation.copilot.previewSuggested')}</div>
                    <div className="font-mono text-sm text-text">{previewItem.suggested?.transaction_type || '—'}</div>
                    <div className="text-xs text-muted">{previewItem.reason || '—'}</div>
                    {previewItem.suggested?.counterparty_name && <div className="text-xs text-muted">{previewItem.suggested.counterparty_name}</div>}
                  </div>
                </div>
              </div>
            ))}
            {canApplyClassificationPreview && applicablePreviewItems.length > 0 && (
              <div className="space-y-3 rounded-md border border-border bg-surface p-3">
                <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-sm font-semibold text-text">{t('investigation.copilot.classificationApplyReview')}</div>
                    <div className="text-xs text-muted">
                      {t('investigation.copilot.classificationApplySummary', {
                        selected: selectedApplicablePreviewItems.length,
                        total: applicablePreviewItems.length,
                      })}
                    </div>
                  </div>
                  <Badge variant="blue">{operatorName || 'analyst'}</Badge>
                </div>
                <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
                  {t('investigation.copilot.classificationApplyReason')}
                  <textarea
                    value={classificationApplyReason}
                    onChange={(event) => setClassificationApplyReason(event.target.value)}
                    placeholder={t('investigation.copilot.classificationApplyReasonPlaceholder')}
                    rows={3}
                    className="min-h-[84px] resize-y rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
                  />
                </label>
                <div className="flex justify-end">
                  <Button
                    onClick={applySelectedClassificationSuggestions}
                    disabled={isApplyingClassificationSuggestions || selectedApplicablePreviewItems.length === 0 || !classificationApplyReason.trim()}
                  >
                    {isApplyingClassificationSuggestions ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                    {isApplyingClassificationSuggestions
                      ? t('investigation.copilot.applyingClassificationSuggestions')
                      : t('investigation.copilot.applySelectedClassificationSuggestions')}
                  </Button>
                </div>
                {classificationApplyError && (
                  <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                    {classificationApplyError}
                  </div>
                )}
                {classificationApplyResult && (
                  <div className="rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
                    {t('investigation.copilot.classificationApplyDone', {
                      count: Number(classificationApplyResult.applied_count || 0),
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Card>

      <Card className="space-y-4">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.taskMode')}
          </div>
          <div className="grid gap-2 md:grid-cols-4">
            {TASK_MODES.map((mode) => {
              const Icon = TASK_MODE_ICONS[mode]
              return (
                <Button
                  key={mode}
                  size="sm"
                  variant={taskMode === mode ? 'primary' : 'outline'}
                  onClick={() => setTaskMode(mode)}
                  className="justify-start"
                >
                  <Icon size={14} />
                  {t(`investigation.copilot.task.${mode}`)}
                </Button>
              )
            })}
          </div>
        </div>
        <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-wide text-muted">
          {t('investigation.copilot.focus')}
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={t('investigation.copilot.focusPlaceholder')}
            rows={5}
            className="min-h-[132px] resize-y rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
          />
        </label>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <label className="flex w-36 flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {t('investigation.copilot.maxTxns')}
            <input
              type="number"
              min="1"
              max="50"
              value={maxTransactions}
              onChange={(event) => setMaxTransactions(event.target.value)}
              className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm normal-case tracking-normal text-text outline-none focus:border-accent"
            />
          </label>
          <Button onClick={submit} disabled={!hasScope(scope) || isAsking}>
            {isAsking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            {isAsking ? t('investigation.copilot.asking') : t('investigation.copilot.ask')}
          </Button>
        </div>
        {error && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}
      </Card>

      {answer && (
        <Card className="space-y-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <CardTitle className="mb-0">
              <ShieldCheck size={18} />
              {t('investigation.copilot.answer')}
            </CardTitle>
            <div className="flex flex-wrap gap-2">
              {answer.task_mode && (
                <Badge variant="blue">
                  {t(`investigation.copilot.task.${answer.task_mode}`, { defaultValue: answer.task_mode })}
                </Badge>
              )}
              <Badge variant={answer.status === 'ok' ? 'green' : 'yellow'}>{answer.status}</Badge>
              <Badge variant={answer.citation_policy?.status === 'ok' ? 'green' : 'yellow'}>
                {answer.citation_policy?.status || 'unknown'}
              </Badge>
            </div>
          </div>
          <div className="whitespace-pre-wrap rounded-lg border border-border bg-surface2 p-4 text-sm leading-6 text-text">
            {answer.answer || t('investigation.copilot.emptyAnswer')}
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('investigation.copilot.model')}</div>
              <div className="font-mono text-xs text-text">{answer.model || '—'}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('investigation.copilot.contextHash')}</div>
              <div className="font-mono text-xs text-text">{shortHash(answer.context_hash || '') || '—'}</div>
            </div>
            <div className="rounded-lg border border-border bg-surface2 px-3 py-2">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('investigation.copilot.auditId')}</div>
              <div className="font-mono text-xs text-text break-all">{answer.audit_id || '—'}</div>
            </div>
          </div>
          {Array.isArray(answer.citations) && answer.citations.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t('investigation.copilot.citations')}</div>
              <div className="flex flex-wrap gap-2">
                {answer.citations.slice(0, 24).map((citation: any) => (
                  <span key={citation.id} className="rounded-full border border-border bg-surface2 px-2.5 py-1 font-mono text-xs text-text2">
                    {citation.id}
                  </span>
                ))}
              </div>
            </div>
          )}
          {Array.isArray(answer.warnings) && answer.warnings.length > 0 && (
            <div className="space-y-1 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
              {answer.warnings.map((warning: string, index: number) => (
                <div key={`${warning}-${index}`}>{warning}</div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
