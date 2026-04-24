import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BrainCircuit, FileText, ListChecks, Loader2, ScrollText, Send, ShieldAlert, ShieldCheck, Sparkles, Target } from 'lucide-react'
import { askCopilot, getCaseTagDetail, listCaseTags, previewClassification, type CaseTagDetail, type CaseTagItem, type CaseTagLinkedObject } from '@/api'
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

const EMPTY_SCOPE: CopilotScope = { parser_run_id: '', file_id: '', account: '', case_tag_id: '', case_tag: '' }
const TASK_MODES: CopilotTaskMode[] = ['account_summary', 'alert_explanation', 'review_checklist', 'draft_report_paragraph']
const TRANSACTION_TYPES = ['IN_TRANSFER', 'OUT_TRANSFER', 'DEPOSIT', 'WITHDRAW', 'FEE', 'SALARY', 'IN_UNKNOWN', 'OUT_UNKNOWN']
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

function normalizeAccount(value: string) {
  return value.replace(/\D/g, '')
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
        max_transactions: Math.max(1, Math.min(50, Number(maxTransactions || 20))),
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

  const previewItem = Array.isArray(classificationPreview?.items) ? classificationPreview.items[0] : null

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
          <div className="flex items-end">
            <Button onClick={submitClassificationPreview} disabled={isPreviewingClassification || !classificationForm.description.trim()}>
              {isPreviewingClassification ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {isPreviewingClassification ? t('investigation.copilot.previewingClassification') : t('investigation.copilot.previewClassificationAction')}
            </Button>
          </div>
        </div>
        {classificationPreviewError && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
            {classificationPreviewError}
          </div>
        )}
        {previewItem && (
          <div className="space-y-3 rounded-lg border border-border bg-surface2 p-3">
            <div className="flex flex-wrap items-center gap-2">
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
