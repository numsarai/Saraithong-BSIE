import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BrainCircuit, FileText, ListChecks, Loader2, ScrollText, Send, ShieldAlert, ShieldCheck } from 'lucide-react'
import { askCopilot } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardTitle } from '@/components/ui/card'

type CopilotScope = {
  parser_run_id: string
  file_id: string
  account: string
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

const EMPTY_SCOPE: CopilotScope = { parser_run_id: '', file_id: '', account: '' }
const TASK_MODES: CopilotTaskMode[] = ['account_summary', 'alert_explanation', 'review_checklist', 'draft_report_paragraph']
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
  return Boolean(scope.parser_run_id.trim() || scope.file_id.trim() || scope.account.trim())
}

function normalizeAccount(value: string) {
  return value.replace(/\D/g, '')
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
  const [answer, setAnswer] = useState<any>(null)
  const [error, setError] = useState('')

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

        <div className="grid gap-3 md:grid-cols-3">
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
        </div>

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
