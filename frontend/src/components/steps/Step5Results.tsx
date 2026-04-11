import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { deleteOverride, generateAccountReport, getOverrides, getResults, getResultsTimeline, saveOverride } from '@/api'
import { normalizeOperatorName, useStore } from '@/store'
import { BankLogo } from '@/components/BankLogo'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { fmt, fmtDate, fmtDateRange } from '@/lib/utils'
import { toast } from 'sonner'
import { Download, RotateCcw, ShieldCheck, History, Trash2 } from 'lucide-react'
import { AccountFlowGraph } from '@/components/AccountFlowGraph'
import { TimelineChart } from '@/components/TimelineChart'
import { TimeWheel } from '@/components/TimeWheel'

type OverrideState = { tid: string; from: string; to: string } | null

function getQuickDiagnosis(reconciliation: any, checkMode: 'file_order' | 'chronological', t: (key: string) => string) {
  const active = reconciliation?.check_modes?.[checkMode] || reconciliation || {}
  if ((reconciliation?.material_mismatched_rows ?? 0) > 0) {
    return t('results.diagnosis.materialMismatch')
  }
  if (reconciliation?.chronology_issue_detected) {
    return t('results.diagnosis.timeOrderIssue')
  }
  if ((reconciliation?.rounding_drift_rows ?? 0) > 0) {
    return t('results.diagnosis.minorDrift')
  }
  if (active?.status === 'VERIFIED') {
    return t('results.diagnosis.normal')
  }
  if (active?.status === 'INFERRED') {
    return t('results.diagnosis.noBalance')
  }
  return t('results.diagnosis.fallback')
}

export function Step5Results() {
  const { t } = useTranslation()
  const { results, account, bankKey, parserRunId, currentTab, setCurrentTab, reset, operatorName } = useStore()
  const resolvedOperatorName = normalizeOperatorName(operatorName)
  const [page, setPage]       = useState(1)
  const [override, setOverride] = useState<OverrideState>(null)
  const [ovForm, setOvForm]   = useState({ from: '', to: '', reason: '', by: resolvedOperatorName })
  const [checkMode, setCheckMode] = useState<'file_order' | 'chronological'>('file_order')

  const { data: txnData, refetch } = useQuery({
    queryKey: ['results', account, parserRunId, page],
    queryFn: () => getResults(account, page, 100, parserRunId),
    enabled: !!account,
  })
  const { data: overrideData, refetch: refetchOverrides } = useQuery({
    queryKey: ['overrides', account],
    queryFn: () => getOverrides(),
    enabled: !!account,
  })
  const { data: timelineData } = useQuery({
    queryKey: ['results-timeline', account, parserRunId],
    queryFn: () => getResultsTimeline(account, parserRunId),
    enabled: !!account,
    staleTime: 60_000,
  })
  const timelineItems = timelineData?.items || []

  const meta = results?.meta || txnData?.meta || {}
  const rows = txnData?.rows || results?.transactions || []
  const total = Number(
    txnData?.total
    ?? meta.num_transactions
    ?? results?.transactions?.length
    ?? rows.length
    ?? 0
  )
  const totalPages = Math.ceil(total / 100) || 1
  const summaryTotal = Number(
    txnData?.total
    ?? meta.num_transactions
    ?? results?.transactions?.length
    ?? rows.length
    ?? 0
  )
  const entityRows = results?.entities || txnData?.entities || []
  const linkRows = results?.links || txnData?.links || []
  const showingPreview =
    !txnData && (
      (results?.transactions?.length ?? 0) > 0 ||
      (results?.entities?.length ?? 0) > 0 ||
      (results?.links?.length ?? 0) > 0
    )
  const overrideRows = Array.isArray(overrideData?.overrides)
    ? overrideData.overrides.filter((row: any) => String(row.account_number || '') === String(account || ''))
    : []

  const dlBase  = `/api/download/${account}`
  const reportFile = meta.report_filename || 'report.xlsx'
  const originalFilename = meta.original_filename || 'original.xlsx'
  const categoryFiles = meta.category_files || {}
  const reconciliation = meta.reconciliation || {}
  const checkModes = reconciliation.check_modes || {}
  const activeCheck = checkModes[checkMode] || {
    status: reconciliation.status || '—',
    mismatched_rows: reconciliation.mismatched_rows ?? '—',
    max_abs_difference: reconciliation.max_abs_difference ?? null,
  }
  const filePrefix = account ? `bsie_${account}` : 'bsie'
  const quickDiagnosis = getQuickDiagnosis(reconciliation, checkMode, t)
  const downloadHref = (file: string, downloadName: string) =>
    `${dlBase}/${encodeURIComponent(file).replace(/%2F/g, '/')}` +
    `?download_name=${encodeURIComponent(downloadName)}`
  const downloads = [
    { label: t('results.downloads.reportXlsx'),        file: `processed/${reportFile}`, downloadName: reportFile },
    { label: t('results.downloads.transactionsCsv'),   file: 'processed/transactions.csv', downloadName: `${filePrefix}_transactions.csv` },
    { label: t('results.downloads.transferInCsv'),    file: `processed/${categoryFiles.transfer_in || 'transfer_in.csv'}`, downloadName: `${filePrefix}_transfer_in.csv` },
    { label: t('results.downloads.transferOutCsv'),   file: `processed/${categoryFiles.transfer_out || 'transfer_out.csv'}`, downloadName: `${filePrefix}_transfer_out.csv` },
    { label: t('results.downloads.depositsCsv'),       file: `processed/${categoryFiles.deposit || 'deposit.csv'}`, downloadName: `${filePrefix}_deposit.csv` },
    { label: t('results.downloads.withdrawalsCsv'),    file: `processed/${categoryFiles.withdraw || 'withdraw.csv'}`, downloadName: `${filePrefix}_withdraw.csv` },
    { label: t('results.downloads.entitiesCsv'),       file: 'processed/entities.csv', downloadName: `${filePrefix}_entities.csv` },
    { label: t('results.downloads.entitiesXlsx'),      file: 'processed/entities.xlsx', downloadName: `${filePrefix}_entities.xlsx` },
    { label: t('results.downloads.linksCsv'),          file: 'processed/links.csv', downloadName: `${filePrefix}_links.csv` },
    { label: t('results.downloads.linksXlsx'),         file: 'processed/links.xlsx', downloadName: `${filePrefix}_links.xlsx` },
    { label: t('results.downloads.graphNodesCsv'),    file: `processed/${categoryFiles.nodes || 'nodes.csv'}`, downloadName: `${filePrefix}_nodes.csv` },
    { label: t('results.downloads.graphEdgesCsv'),    file: `processed/${categoryFiles.edges || 'edges.csv'}`, downloadName: `${filePrefix}_edges.csv` },
    { label: t('results.downloads.graphAggregateCsv'), file: `processed/${categoryFiles.aggregated_edges || 'aggregated_edges.csv'}`, downloadName: `${filePrefix}_aggregated_edges.csv` },
    { label: t('results.downloads.graphManifestJson'), file: `processed/${categoryFiles.graph_manifest || 'graph_manifest.json'}`, downloadName: `${filePrefix}_graph_manifest.json` },
    { label: t('results.downloads.graphAnalysisJson'), file: `processed/${categoryFiles.graph_analysis || 'graph_analysis.json'}`, downloadName: `${filePrefix}_graph_analysis.json` },
    { label: t('results.downloads.graphAnalysisXlsx'), file: `processed/${categoryFiles.graph_analysis_workbook || 'graph_analysis.xlsx'}`, downloadName: `${filePrefix}_graph_analysis.xlsx` },
    { label: t('results.downloads.reconciliationCsv'), file: `processed/${categoryFiles.reconciliation || 'reconciliation.csv'}`, downloadName: `${filePrefix}_reconciliation.csv` },
    { label: t('results.downloads.reconciliationXlsx'), file: 'processed/reconciliation.xlsx', downloadName: `${filePrefix}_reconciliation.xlsx` },
    { label: t('results.downloads.accountOfx'),    file: `processed/${categoryFiles.ofx || 'account.ofx'}`, downloadName: `${filePrefix}.ofx` },
    { label: t('results.downloads.i2Chart'),       file: 'processed/i2_chart.anx', downloadName: `${filePrefix}_i2_chart.anx` },
    { label: t('results.downloads.i2ImportCsv'), file: `processed/${categoryFiles.i2_import_csv || 'i2_import_transactions.csv'}`, downloadName: `${filePrefix}_i2_import_transactions.csv` },
    { label: t('results.downloads.i2ImportSpec'), file: `processed/${categoryFiles.i2_import_spec || 'i2_import_spec.ximp'}`, downloadName: `${filePrefix}_i2_import_spec.ximp` },
    { label: t('results.downloads.originalSource'),       file: `raw/original${originalFilename.includes('.') ? originalFilename.slice(originalFilename.lastIndexOf('.')) : '.xlsx'}`, downloadName: originalFilename },
    { label: t('results.downloads.metadataJson'),      file: 'meta.json', downloadName: `${filePrefix}_meta.json` },
  ]

  useEffect(() => {
    setCheckMode(reconciliation.recommended_check_mode === 'chronological' ? 'chronological' : 'file_order')
  }, [account, reconciliation.recommended_check_mode])

  const statCards = [
    { label: t('results.stats.totalTxn'),   value: String(meta.num_transactions ?? total),          color: '' },
    { label: t('results.stats.totalIn'),       value: `฿${fmt(meta.total_in  || 0)}`,                  color: 'text-success' },
    { label: t('results.stats.totalOut'),      value: `฿${fmt(meta.total_out || 0)}`,                  color: 'text-danger' },
    { label: t('results.stats.circulation'),    value: `฿${fmt(meta.total_circulation || 0)}`,           color: 'text-accent' },
    { label: t('results.stats.transferIn'),    value: String(meta.category_counts?.transfer_in ?? '—'), color: '' },
    { label: t('results.stats.transferOut'),   value: String(meta.category_counts?.transfer_out ?? '—'), color: '' },
    { label: t('results.stats.deposits'),       value: String(meta.category_counts?.deposit ?? '—'),      color: '' },
    { label: t('results.stats.withdrawals'),    value: String(meta.category_counts?.withdraw ?? '—'),     color: '' },
    { label: t('results.stats.dateRange'),     value: fmtDateRange(meta.date_range),                    color: '' },
    { label: t('results.stats.checkView'),     value: checkMode === 'chronological' ? t('results.chronological') : t('results.fileOrder'), color: 'text-accent' },
    { label: t('results.stats.balanceCheck'),  value: activeCheck.status || '—',                        color: activeCheck.status === 'VERIFIED' ? 'text-success' : activeCheck.status === 'FAILED' ? 'text-danger' : 'text-accent' },
    { label: t('results.stats.mismatches'),     value: String(activeCheck.mismatched_rows ?? '—'),       color: activeCheck.mismatched_rows ? 'text-danger' : '' },
    { label: t('results.stats.maxDiff'),       value: activeCheck.max_abs_difference != null ? `฿${fmt(activeCheck.max_abs_difference)}` : '—', color: (activeCheck.max_abs_difference ?? 0) > 0 ? 'text-warning' : '' },
    { label: t('results.stats.timeOrder'),     value: reconciliation.chronology_issue_detected ? t('results.reviewNeeded') : t('results.ok'), color: reconciliation.chronology_issue_detected ? 'text-warning' : '' },
    { label: t('results.stats.sortedMismatch'), value: String(reconciliation.chronological_mismatched_rows ?? '—'), color: (reconciliation.chronological_mismatched_rows ?? 0) ? 'text-accent' : '' },
    { label: t('results.stats.driftRows'),     value: String(reconciliation.rounding_drift_rows ?? '—'), color: (reconciliation.rounding_drift_rows ?? 0) ? 'text-warning' : '' },
    { label: t('results.stats.unknownCPs'),    value: String(meta.num_unknown ?? '—'),                  color: '' },
    { label: t('results.stats.partialAccts'),  value: String(meta.num_partial_accounts ?? '—'),         color: '' },
  ]

  const openOverride = (row: any) => {
    setOverride({ tid: row.transaction_id, from: row.from_account || '', to: row.to_account || '' })
    setOvForm({ from: row.from_account || '', to: row.to_account || '', reason: '', by: resolvedOperatorName })
  }

  const handleSaveOverride = async () => {
    if (!override) return
    try {
      await saveOverride({
        account_number: account,
        transaction_id: override.tid,
        from_account: ovForm.from,
        to_account: ovForm.to,
        reason: ovForm.reason,
        override_by: normalizeOperatorName(ovForm.by),
      })
      toast.success(t('results.toast.overrideSaved'))
      setOverride(null)
      refetch()
      refetchOverrides()
    } catch (e: any) { toast.error(e.message) }
  }

  const handleDeleteOverride = async (transactionId: string) => {
    const confirmed = window.confirm(
      `Delete the scoped override for ${transactionId} on account ${account || 'UNKNOWN'}?`
    )
    if (!confirmed) return

    const deletedOverride = overrideRows.find((row: any) => row.transaction_id === transactionId)

    try {
      await deleteOverride(transactionId, account, resolvedOperatorName)
      refetch()
      refetchOverrides()
      toast(t('results.toast.overrideRemoved'), {
        description: `Scoped override removed from account ${account || 'UNKNOWN'}.`,
        action: deletedOverride ? {
          label: 'Undo',
          onClick: async () => {
            try {
              await saveOverride({
                account_number: account,
                transaction_id: deletedOverride.transaction_id,
                from_account: deletedOverride.override_from_account,
                to_account: deletedOverride.override_to_account,
                reason: deletedOverride.override_reason || '',
                override_by: deletedOverride.override_by || resolvedOperatorName,
              })
              toast.success(t('results.toast.overrideRestored'))
              refetch()
              refetchOverrides()
            } catch (e: any) {
              toast.error(e.message)
            }
          },
        } : undefined,
      })
    } catch (e: any) {
      toast.error(e.message)
    }
  }

  const TABS = ['transactions', 'entities', 'links'] as const

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BankLogo bank={{ key: bankKey || String(meta.bank || '').toLowerCase(), name: meta.bank || bankKey || 'Bank' }} size="lg" />
          <div>
          <h2 className="text-lg font-bold text-text">{t('results.title')}</h2>
          <p className="text-muted text-sm">{account} · {meta.bank || ''} · {summaryTotal} {t('results.transactions')}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={reset}>
          <RotateCcw size={13} />{t('results.processAnother')}
        </Button>
      </div>

      {/* Downloads */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2">
        {downloads.map(d => (
          <a
            key={d.file}
            href={downloadHref(d.file, d.downloadName)}
            download={d.downloadName}
            className="flex items-center gap-2 px-3 py-2.5 bg-surface2 border border-border rounded-lg text-accent text-sm hover:border-accent transition-all"
          >
            <Download size={13} />{d.label}
          </a>
        ))}
        <button
          onClick={() => generateAccountReport(account, parserRunId || undefined, resolvedOperatorName).catch(e => toast.error(e.message))}
          className="flex items-center gap-2 px-3 py-2.5 bg-accent/20 border border-accent/40 rounded-lg text-accent text-sm hover:bg-accent/30 transition-all cursor-pointer font-semibold"
        >
          <Download size={13} />{t('results.downloads.reportPdf')}
        </button>
      </div>

      {showingPreview ? (
        <Card className="border-accent/20 bg-accent/[0.06] p-3">
          <div className="flex items-center gap-2 text-sm text-text2">
            <Badge variant="blue">{t('results.preview')}</Badge>
            <span>{t('results.previewHint')}</span>
          </div>
        </Card>
      ) : null}

      <Card className="bg-success/[0.06] border-success/20 p-4">
        <CardTitle className="mb-2 text-text">
          <ShieldCheck size={15} className="text-success" />
          {t('results.overrideScope')}
        </CardTitle>
        <p className="text-sm text-text2">
          {t('results.overrideScopeHint')} <span className="font-mono">{account || 'UNKNOWN'}</span> {t('results.overrideScopeHint2')}
        </p>
      </Card>

      <Card className="p-4">
        <CardTitle className="mb-3 text-text">
          <History size={15} className="text-accent" />
          {t('results.overrideHistory')}
        </CardTitle>
        {overrideRows.length > 0 ? (
          <div className="space-y-2">
            {overrideRows.map((row: any) => (
              <div key={`${row.account_number}:${row.transaction_id}`} className="rounded-lg border border-border bg-surface2 px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-mono text-sm text-text">{row.transaction_id}</div>
                    <div className="text-xs text-muted">
                      {row.override_from_account || '—'} {'->'} {row.override_to_account || '—'}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="blue">{t('results.scoped')}</Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDeleteOverride(row.transaction_id)}
                    >
                      <Trash2 size={12} />
                      {t('results.delete')}
                    </Button>
                  </div>
                </div>
                <div className="mt-2 text-xs text-text2">
                  {row.override_reason || 'No reason provided'}
                </div>
                <div className="mt-1 text-[11px] text-muted">
                  {row.override_by || 'Unknown operator'} · {row.override_timestamp ? fmtDate(row.override_timestamp) : 'Unknown time'}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">
            {t('results.noOverrides')} <span className="font-mono">{account || 'UNKNOWN'}</span>.
          </p>
        )}
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(130px,1fr))] gap-3">
        {statCards.map(s => (
          <div key={s.label} className="bg-surface border border-border rounded-xl p-4">
            <div className="text-[11px] uppercase text-muted mb-1 font-semibold">{s.label}</div>
            <div className={`text-xl font-bold ${s.color || 'text-text'}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {rows.length > 0 && (
        <AccountFlowGraph account={account} bankKey={bankKey} rows={rows} />
      )}

      {timelineItems.length > 0 && (
        <TimelineChart transactions={timelineItems} />
      )}

      {timelineItems.length > 0 && (
        <TimeWheel transactions={timelineItems} />
      )}

      <Card className="border-accent/20 bg-accent/[0.06] p-4">
        <CardTitle className="mb-2 text-text">{t('results.userSummary')}</CardTitle>
        <p className="text-sm text-text2">{quickDiagnosis}</p>
      </Card>

      {/* Reconciliation summary */}
      <div className="rounded-xl border border-border bg-surface p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-text">{t('results.balanceReconciliation')}</h3>
            <p className="text-xs text-muted">
              {t('results.balanceReconciliationHint')}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg border border-border bg-surface2 p-1">
              <button
                onClick={() => setCheckMode('file_order')}
                className={[
                  'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                  checkMode === 'file_order' ? 'bg-accent text-white' : 'text-text2 hover:bg-surface',
                ].join(' ')}
              >
                {t('results.fileOrder')}
              </button>
              <button
                onClick={() => setCheckMode('chronological')}
                className={[
                  'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                  checkMode === 'chronological' ? 'bg-accent text-white' : 'text-text2 hover:bg-surface',
                ].join(' ')}
              >
                {t('results.chronological')}
              </button>
            </div>
            <Badge
              variant={
                activeCheck.status === 'VERIFIED'
                  ? 'green'
                  : activeCheck.status === 'FAILED'
                    ? 'red'
                    : 'blue'
              }
            >
              {activeCheck.status || 'UNKNOWN'}
            </Badge>
          </div>
        </div>
        <div className="mt-3 rounded-lg border border-border bg-surface2 px-3 py-2 text-xs text-text2 space-y-1">
          <div>
            {t('results.recommendedView')} <span className="font-semibold text-text">{reconciliation.recommended_check_mode === 'chronological' ? t('results.chronological') : t('results.fileOrder')}</span>
          </div>
          <div>
            {t('results.viewChangeNote')}
          </div>
        </div>
        <div className="mt-3 grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-3 text-sm">
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">{t('results.matchedRows')}</div>
            <div className="text-text font-semibold">{reconciliation.matched_rows ?? '—'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">{t('results.missingBalanceRows')}</div>
            <div className="text-text font-semibold">{reconciliation.missing_balance_rows ?? '—'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">{t('results.openingBalance')}</div>
            <div className="text-text font-semibold">
              {reconciliation.opening_balance != null ? `฿${fmt(reconciliation.opening_balance)}` : '—'}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">{t('results.closingBalance')}</div>
            <div className="text-text font-semibold">
              {reconciliation.closing_balance != null ? `฿${fmt(reconciliation.closing_balance)}` : '—'}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">{t('results.chronologicalMismatches')}</div>
            <div className="text-text font-semibold">{reconciliation.chronological_mismatched_rows ?? '—'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">Reduced By Sorting</div>
            <div className="text-text font-semibold">{reconciliation.mismatches_reduced_by_sorting ?? '—'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">{t('results.roundingDriftRows')}</div>
            <div className="text-text font-semibold">{reconciliation.rounding_drift_rows ?? '—'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">Material Mismatches</div>
            <div className="text-text font-semibold">{reconciliation.material_mismatched_rows ?? '—'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">Missing Time Rows</div>
            <div className="text-text font-semibold">{reconciliation.missing_time_rows ?? '—'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase text-muted font-semibold">Duplicate Time Rows</div>
            <div className="text-text font-semibold">{reconciliation.duplicate_timestamp_rows ?? '—'}</div>
          </div>
        </div>
        {(reconciliation.chronology_issue_detected || (reconciliation.rounding_drift_rows ?? 0) > 0) && (
          <div className="mt-3 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-text2 space-y-1">
            {reconciliation.chronology_issue_detected && (
              <div>
                Some statement rows are likely out of chronological order. Review the source statement order before treating this as a true balance break.
              </div>
            )}
            {(reconciliation.rounding_drift_rows ?? 0) > 0 && (
              <div>
                Small drift rows may reflect rounding or minor statement-side adjustments rather than a major parsing error.
              </div>
            )}
          </div>
        )}
        {Array.isArray(reconciliation.notes) && reconciliation.notes.length > 0 && (
          <div className="mt-3 rounded-lg border border-border bg-surface2 px-3 py-2 text-xs text-muted space-y-1">
            {reconciliation.notes.map((note: string, idx: number) => (
              <div key={idx}>{note}</div>
            ))}
          </div>
        )}
        {Array.isArray(reconciliation.guidance_th) && reconciliation.guidance_th.length > 0 && (
          <div className="mt-3 rounded-lg border border-accent/20 bg-accent/[0.06] px-3 py-2 text-xs text-text2 space-y-1">
            <div className="font-semibold text-text">คำแนะนำสำหรับผู้ใช้งาน</div>
            {reconciliation.guidance_th.map((note: string, idx: number) => (
              <div key={idx}>- {note}</div>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-border">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setCurrentTab(tab)}
            className={[
              'px-4 py-2 text-sm font-medium capitalize transition-all border-b-2 -mb-px',
              currentTab === tab
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-text2',
            ].join(' ')}
          >
            {t(`results.tabs.${tab}`)}
          </button>
        ))}
      </div>

      {/* Transactions tab */}
      {currentTab === 'transactions' && (
        <div className="space-y-3">
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-xs border-collapse" style={{ minWidth: 900 }}>
              <thead>
                <tr className="bg-surface2">
                  {['ID','Date','Amount','Dir','Type','Conf','CP Account','CP Name','Description','From','To',''].map((h, idx) => (
                    <th key={idx} className="py-2 px-2 text-left text-[10px] uppercase text-muted border-b border-border font-semibold whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any) => (
                  <tr
                    key={row.transaction_id}
                    className={['border-b border-border/40 hover:bg-accent/[0.04] transition-colors', row.is_overridden ? 'bg-success/5' : ''].join(' ')}
                  >
                    <td className="py-1.5 px-2 font-mono text-muted">{row.transaction_id}</td>
                    <td className="py-1.5 px-2 text-text2 whitespace-nowrap">{fmtDate(row.date)}</td>
                    <td className={`py-1.5 px-2 font-mono font-bold ${row.direction === 'IN' ? 'text-success' : 'text-danger'}`}>
                      {row.direction === 'IN' ? '+' : '-'}{fmt(Math.abs(row.amount || 0))}
                    </td>
                    <td className="py-1.5 px-2">
                      <Badge variant={row.direction === 'IN' ? 'green' : 'red'}>{row.direction}</Badge>
                    </td>
                    <td className="py-1.5 px-2 text-text2">{row.transaction_type}</td>
                    <td className="py-1.5 px-2 text-muted">{Math.round((row.confidence || 0) * 100)}%</td>
                    <td className="py-1.5 px-2 font-mono text-text2 max-w-[120px] truncate">{row.counterparty_account || '—'}</td>
                    <td className="py-1.5 px-2 text-text2 max-w-[100px] truncate">{row.counterparty_name || '—'}</td>
                    <td className="py-1.5 px-2 text-muted max-w-[150px] truncate">{row.description}</td>
                    <td className="py-1.5 px-2 font-mono text-text2 max-w-[100px] truncate">{row.from_account || '—'}</td>
                    <td className="py-1.5 px-2 font-mono text-text2 max-w-[100px] truncate">{row.to_account || '—'}</td>
                    <td className="py-1.5 px-2">
                      <button
                        onClick={() => openOverride(row)}
                        className="text-[10px] text-accent border border-accent/30 rounded px-1.5 py-0.5 hover:bg-accent/10 transition-colors"
                      >
                        {row.is_overridden ? 'Edit' : 'Override'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          <div className="flex items-center gap-2 text-sm text-muted">
            <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</Button>
            <span>Page {page} of {totalPages} · {total} rows</span>
            <Button size="sm" variant="ghost" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</Button>
          </div>
        </div>
      )}

      {/* Entities tab */}
      {currentTab === 'entities' && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-surface2">
                {['Entity ID','Type','Value','Count','First Seen','Last Seen'].map(h => (
                  <th key={h} className="py-2 px-3 text-left text-[10px] uppercase text-muted border-b border-border font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entityRows.map((e: any) => (
                <tr key={e.entity_id} className="border-b border-border/40 hover:bg-accent/[0.04]">
                  <td className="py-1.5 px-3 font-mono text-muted text-[10px]">{e.entity_id}</td>
                  <td className="py-1.5 px-3"><Badge variant="blue">{e.entity_type}</Badge></td>
                  <td className="py-1.5 px-3 text-text2">{e.value}</td>
                  <td className="py-1.5 px-3 text-text2">{e.count}</td>
                  <td className="py-1.5 px-3 text-muted">{fmtDate(e.first_seen)}</td>
                  <td className="py-1.5 px-3 text-muted">{fmtDate(e.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Links tab */}
      {currentTab === 'links' && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-surface2">
                {['Txn ID','From','To','Amount','Date','Type'].map(h => (
                  <th key={h} className="py-2 px-3 text-left text-[10px] uppercase text-muted border-b border-border font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {linkRows.map((l: any, i: number) => (
                <tr key={i} className="border-b border-border/40 hover:bg-accent/[0.04]">
                  <td className="py-1.5 px-3 font-mono text-muted text-[10px]">{l.transaction_id}</td>
                  <td className="py-1.5 px-3 font-mono text-text2">{l.from_account}</td>
                  <td className="py-1.5 px-3 font-mono text-text2">{l.to_account}</td>
                  <td className="py-1.5 px-3 text-success font-mono">฿{fmt(Math.abs(l.amount || 0))}</td>
                  <td className="py-1.5 px-3 text-muted">{fmtDate(l.date)}</td>
                  <td className="py-1.5 px-3 text-text2">{l.transaction_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Override Modal */}
      {override && (
        <div
          className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4"
          onClick={() => setOverride(null)}
        >
          <div
            className="bg-surface border border-border rounded-xl p-6 w-full max-w-[500px] shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-base font-bold mb-4 text-text">{t('results.overrideModal.title')}</h3>
            <div className="mb-4 rounded-lg border border-success/20 bg-success/[0.06] px-3 py-2 text-xs text-text2">
              This override will apply only to account <span className="font-mono">{account || 'UNKNOWN'}</span>.
            </div>
            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] uppercase text-muted font-semibold">{t('results.overrideModal.transactionId')}</label>
                <input
                  value={override.tid} readOnly
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-muted"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                {(['from','to'] as const).map(k => (
                  <div key={k} className="flex flex-col gap-1">
                    <label className="text-[11px] uppercase text-muted font-semibold">{k === 'from' ? t('results.overrideModal.fromAccount') : t('results.overrideModal.toAccount')}</label>
                    <input
                      value={ovForm[k]}
                      onChange={e => setOvForm(f => ({ ...f, [k]: e.target.value }))}
                      className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
                    />
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] uppercase text-muted font-semibold">{t('results.overrideModal.reason')}</label>
                <input
                  value={ovForm.reason}
                  onChange={e => setOvForm(f => ({ ...f, reason: e.target.value }))}
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] uppercase text-muted font-semibold">Override By</label>
                <input
                  value={ovForm.by}
                  onChange={e => setOvForm(f => ({ ...f, by: e.target.value }))}
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <Button variant="ghost" onClick={() => setOverride(null)}>{t('results.overrideModal.cancel')}</Button>
              <Button variant="primary" onClick={handleSaveOverride}>{t('results.overrideModal.save')}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
