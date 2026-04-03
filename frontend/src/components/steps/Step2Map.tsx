import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import { confirmMapping, getBanks, learnBank } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardTitle } from '@/components/ui/card'
import { evaluateReviewGate } from '@/lib/reviewGate'
import { toast } from 'sonner'
import { ChevronLeft, ChevronRight, Wand2, X, BookPlus, ArrowRight, ArrowLeftRight, Building2, Wallet, CircleDashed, FileSearch, BrainCircuit, DatabaseZap, ShieldAlert, ShieldCheck } from 'lucide-react'

const FIELDS = [
  { key: 'date',                 label: 'Date',                required: true  },
  { key: 'time',                 label: 'Time',                required: false },
  { key: 'description',          label: 'Description',         required: true  },
  { key: 'amount',               label: 'Amount (signed)',      required: false },
  { key: 'debit',                label: 'Debit / Withdraw',     required: false },
  { key: 'credit',               label: 'Credit / Deposit',     required: false },
  { key: 'balance',              label: 'Balance',              required: false },
  { key: 'channel',              label: 'Channel',              required: false },
  { key: 'counterparty_account', label: 'Counterparty Account', required: false },
  { key: 'counterparty_name',    label: 'Counterparty Name',    required: false },
]

export function Step2Map() {
  const {
    detectedBank, allColumns, suggestedMapping, confirmedMapping,
    setConfirmedMapping, sampleRows, bankKey, setBankKey, setStep, confidenceScores,
    headerRow, sheetName, memoryMatch, bankMemoryMatch,
    bankReviewed, mappingReviewed, setBankReviewed, setMappingReviewed,
    isBlockedCase, canProceedToConfig,
  } = useStore()
  const [saving, setSaving]         = useState(false)
  const [banks, setBanks]           = useState<any[]>([])
  const [learnOpen, setLearnOpen]   = useState(false)
  const [learnForm, setLearnForm]   = useState({
    key: '', bank_name: '', format_type: 'standard', amount_mode: 'signed',
  })
  const [learning, setLearning]     = useState(false)

  useEffect(() => {
    getBanks().then(setBanks).catch((e) => toast.error(`Could not load banks: ${e.message}`))
  }, [])

  const update = (field: string, value: string) => {
    const nextMapping = { ...confirmedMapping, [field]: value || null }
    const criticalField = field === 'date' || field === 'description' || field === 'amount' || field === 'debit' || field === 'credit'
    if (criticalField && mappingReviewed) {
      setMappingReviewed(false)
    }
    setConfirmedMapping(nextMapping)
  }

  const autoFill = () => {
    if (mappingReviewed) {
      setMappingReviewed(false)
    }
    setConfirmedMapping({ ...suggestedMapping })
  }
  const clearAll = () => {
    const cleared: Record<string, null> = {}
    FIELDS.forEach(f => { cleared[f.key] = null })
    if (mappingReviewed) {
      setMappingReviewed(false)
    }
    setConfirmedMapping(cleared)
  }

  const handleConfirm = async () => {
    if (!canProceedToConfig) {
      toast.error('Resolve the analyst review gate before continuing')
      return
    }
    if (!confirmedMapping['date'])        { toast.error('Date field is required'); return }
    if (!confirmedMapping['description']) { toast.error('Description field is required'); return }
    setSaving(true)
    try {
      await confirmMapping(bankKey, confirmedMapping, allColumns, headerRow, sheetName)
      setStep(3)
      toast.success('Mapping saved')
    } catch (e: any) {
      toast.error(`Failed: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleLearn = async () => {
    if (!learnForm.key.trim())       { toast.error('Bank key is required'); return }
    if (!learnForm.bank_name.trim()) { toast.error('Bank name is required'); return }
    if (!confirmedMapping['date'])   { toast.error('Map at least the Date field first'); return }
    setLearning(true)
    try {
      await learnBank({
        key: learnForm.key.trim().toLowerCase().replace(/\s+/g, '_'),
        bank_name: learnForm.bank_name.trim(),
        format_type: learnForm.format_type,
        amount_mode: learnForm.amount_mode,
        confirmed_mapping: confirmedMapping,
        all_columns: allColumns,
      })
      // Refresh bank list
      const updated = await getBanks()
      setBanks(updated)
      setBankKey(learnForm.key.trim().toLowerCase().replace(/\s+/g, '_'))
      setLearnOpen(false)
      toast.success(`Bank "${learnForm.bank_name}" saved! Auto-detected next time.`)
    } catch (e: any) {
      toast.error(`Failed: ${e.message}`)
    } finally {
      setLearning(false)
    }
  }

  const mappedCount = Object.values(confirmedMapping).filter(Boolean).length
  const reviewGate = evaluateReviewGate({
    detectedBank,
    mapping: confirmedMapping,
    bankReviewed,
    mappingReviewed,
  })
  const confidence  = reviewGate.confidencePercent
  const hasSignedAmount = !!confirmedMapping['amount']
  const hasDebitCredit = !!confirmedMapping['debit'] || !!confirmedMapping['credit']
  const hasCounterparty = !!confirmedMapping['counterparty_account'] || !!confirmedMapping['counterparty_name']
  const amountModeLabel = hasSignedAmount ? 'Signed Amount Mode' : hasDebitCredit ? 'Debit / Credit Mode' : 'Amount Not Mapped'
  const counterpartyLabel = hasCounterparty ? 'Counterparty mapped' : 'Counterparty not mapped yet'
  const candidateKeys = Array.isArray(detectedBank?.top_candidates) ? detectedBank.top_candidates : []
  const rankedCandidates = candidateKeys.map((key: string) => ({
    key,
    name: banks.find((bank: any) => bank.key === key)?.name || key.toUpperCase(),
    score: Number(detectedBank?.scores?.[key] || 0),
    selected: key === bankKey,
  }))
  const positiveEvidence = Array.isArray(detectedBank?.evidence?.positive) ? detectedBank.evidence.positive.slice(0, 6) : []
  const negativeEvidence = Array.isArray(detectedBank?.evidence?.negative) ? detectedBank.evidence.negative.slice(0, 4) : []

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h2 className="text-lg font-bold mb-1 text-text">Detect & Map Columns</h2>
        <p className="text-muted text-sm">Review auto-detected mappings and correct if needed.</p>
      </div>

      {/* Detection summary + Manual Bank Select */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="!p-4 col-span-1">
          <div className="text-[11px] uppercase text-muted mb-2 font-semibold">Bank</div>
          <select
            value={bankKey}
            onChange={e => setBankKey(e.target.value)}
            className="bg-surface3 border border-border rounded-lg px-2 py-1.5 text-sm text-text w-full focus:border-accent outline-none cursor-pointer mb-2"
          >
            {banks.map((b: any) => <option key={b.key} value={b.key}>{b.name}</option>)}
          </select>
          <div className="flex items-center gap-1.5">
            {confidence >= 60
              ? <span className="text-xs text-success">✓ Auto-detected ({confidence}%)</span>
              : <span className="text-xs text-warning">⚠ Low confidence ({confidence}%) — verify bank</span>
            }
          </div>
        </Card>
        <Card className="!p-4">
          <div className="text-[11px] uppercase text-muted mb-1 font-semibold">Columns Found</div>
          <div className="text-lg font-bold text-text">{allColumns.length}</div>
          <div className="text-xs text-muted mt-1">{mappedCount} of {FIELDS.length} fields mapped</div>
        </Card>
        <Card className="!p-4 flex flex-col justify-between">
          <div>
            <div className="text-[11px] uppercase text-muted mb-1 font-semibold">New Bank?</div>
            <div className="text-xs text-muted">Map columns then save as a template for future auto-detection.</div>
          </div>
          <Button size="sm" variant="outline" className="mt-3" onClick={() => {
            setLearnForm({ key: '', bank_name: '', format_type: 'standard', amount_mode: 'signed' })
            setLearnOpen(true)
          }}>
            <BookPlus size={13} />Learn New Bank
          </Button>
        </Card>
      </div>

      <Card>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <CardTitle className="!mb-1">Detection Review</CardTitle>
            <p className="text-sm text-muted">
              Analyst view of the sheet/header chosen, ranked bank candidates, and the evidence used for auto-detection.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5 justify-end">
            <Badge variant="gray">Sheet: {sheetName || 'Unknown'}</Badge>
            <Badge variant="gray">Header Row: {headerRow + 1}</Badge>
            <Badge variant={detectedBank?.ambiguous ? 'red' : confidence >= 75 ? 'green' : 'blue'}>
              {detectedBank?.ambiguous ? 'Analyst Review Needed' : 'Detection Stable'}
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-border bg-surface2/50 p-4">
            <div className="flex items-center gap-2 mb-3 text-text2">
              <FileSearch size={14} className="text-accent" />
              <span className="text-sm font-semibold">Workbook Context</span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted">Detected Bank</span>
                <span className="font-medium text-text">{detectedBank?.bank || 'UNKNOWN'}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted">Confidence</span>
                <span className="font-medium text-text">{confidence}%</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted">Observed Layout</span>
                <span className="font-medium text-text">{formatEvidenceItem(detectedBank?.evidence?.layout || 'unknown')}</span>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {bankMemoryMatch && (
                <div className="rounded-lg border border-success/25 bg-success/[0.06] p-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-text2">
                    <BrainCircuit size={13} className="text-success" />
                    <span>Bank fingerprint matched</span>
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {bankMemoryMatch.bank_key} via {formatEvidenceItem(bankMemoryMatch.match_type || 'memory')} ({Math.round(Number(bankMemoryMatch.match_score || 0) * 100)}%)
                  </div>
                </div>
              )}
              {memoryMatch && (
                <div className="rounded-lg border border-accent/25 bg-accent/[0.06] p-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-text2">
                    <DatabaseZap size={13} className="text-accent" />
                    <span>Column mapping memory matched</span>
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    Profile {memoryMatch.profile_id} reused from {memoryMatch.bank} ({memoryMatch.usage_count} prior uses)
                  </div>
                </div>
              )}
              {!bankMemoryMatch && !memoryMatch && (
                <div className="rounded-lg border border-border/70 bg-surface p-3 text-xs text-muted">
                  No prior memory hit. Detection is based on workbook structure and bank signatures only.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-surface2/50 p-4">
            <div className="flex items-center gap-2 mb-3 text-text2">
              <ArrowLeftRight size={14} className="text-accent" />
              <span className="text-sm font-semibold">Top Candidates</span>
            </div>
            <div className="space-y-2">
              {rankedCandidates.map((candidate: { key: string; name: string; score: number; selected: boolean }) => (
                <div key={candidate.key} className={`rounded-lg border px-3 py-2 ${candidate.selected ? 'border-accent/40 bg-accent/[0.06]' : 'border-border/70 bg-surface'}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text">{candidate.name}</span>
                      {candidate.selected && <Badge variant="blue">Selected</Badge>}
                    </div>
                    <span className="text-xs text-muted">score {candidate.score.toFixed(2)}</span>
                  </div>
                </div>
              ))}
              {rankedCandidates.length === 0 && (
                <div className="rounded-lg border border-border/70 bg-surface p-3 text-xs text-muted">
                  No ranked candidates returned.
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-surface2/50 p-4">
            <div className="flex items-center gap-2 mb-3 text-text2">
              <BrainCircuit size={14} className="text-accent" />
              <span className="text-sm font-semibold">Evidence</span>
            </div>
            <div className="space-y-3">
              <div>
                <div className="text-[11px] uppercase text-muted font-semibold mb-2">Positive</div>
                <div className="flex flex-wrap gap-1.5">
                  {positiveEvidence.map((item: string) => (
                    <span key={item} className="rounded-full border border-success/20 bg-success/10 px-2 py-1 text-[11px] text-success">
                      {formatEvidenceItem(item)}
                    </span>
                  ))}
                  {positiveEvidence.length === 0 && <span className="text-xs text-muted">No positive evidence recorded.</span>}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase text-muted font-semibold mb-2">Negative / Warning</div>
                <div className="flex flex-wrap gap-1.5">
                  {negativeEvidence.map((item: string) => (
                    <span key={item} className="rounded-full border border-warning/20 bg-warning/10 px-2 py-1 text-[11px] text-warning">
                      {formatEvidenceItem(item)}
                    </span>
                  ))}
                  {negativeEvidence.length === 0 && <span className="text-xs text-muted">No negative evidence recorded.</span>}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <CardTitle className="!mb-1">Analyst Decision</CardTitle>
            <p className="text-sm text-muted">
              Weak or ambiguous uploads must be explicitly cleared before the pipeline can continue.
            </p>
          </div>
          <Badge variant={canProceedToConfig ? 'green' : isBlockedCase ? 'red' : 'blue'}>
            {canProceedToConfig ? 'Gate Cleared' : isBlockedCase ? 'Blocked' : 'Ready'}
          </Badge>
        </div>

        {isBlockedCase ? (
          <div className="mb-4 rounded-xl border border-warning/30 bg-warning/10 p-4">
            <div className="flex items-center gap-2 text-text2 mb-2">
              <ShieldAlert size={16} className="text-warning" />
              <span className="text-sm font-semibold">Analyst review required before Step 3</span>
            </div>
            <div className="space-y-1">
              {reviewGate.blockingReasons.map((reason) => (
                <div key={reason} className="text-xs text-muted leading-relaxed">{reason}</div>
              ))}
            </div>
          </div>
        ) : (
          <div className="mb-4 rounded-xl border border-success/25 bg-success/[0.08] p-4">
            <div className="flex items-center gap-2 text-text2 mb-1">
              <ShieldCheck size={16} className="text-success" />
              <span className="text-sm font-semibold">No blocking risk detected</span>
            </div>
            <div className="text-xs text-muted">
              This case meets the current confidence and critical-mapping thresholds, so the review gate is already satisfied.
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-border bg-surface2/50 p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <div className="text-sm font-semibold text-text">Confirm Selected Bank</div>
                <div className="text-xs text-muted">Required when bank detection is ambiguous or below 75% confidence.</div>
              </div>
              <Badge variant={bankReviewed ? 'green' : reviewGate.bankNeedsReview ? 'red' : 'gray'}>
                {bankReviewed ? 'Confirmed' : reviewGate.bankNeedsReview ? 'Required' : 'Auto-cleared'}
              </Badge>
            </div>
            <Button
              size="sm"
              variant={bankReviewed ? 'outline' : 'primary'}
              disabled={!bankKey}
              onClick={() => {
                setBankReviewed(true)
                toast.success('Bank selection confirmed')
              }}
            >
              {bankReviewed ? 'Bank Confirmed' : 'Confirm Selected Bank'}
            </Button>
          </div>

          <div className="rounded-xl border border-border bg-surface2/50 p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <div className="text-sm font-semibold text-text">Confirm Mapping Readiness</div>
                <div className="text-xs text-muted">Map Date, Description, and one amount path before confirming.</div>
              </div>
              <Badge variant={mappingReviewed ? 'green' : reviewGate.mappingNeedsReview ? 'red' : 'gray'}>
                {mappingReviewed ? 'Confirmed' : reviewGate.mappingNeedsReview ? 'Required' : 'Auto-cleared'}
              </Badge>
            </div>
            <Button
              size="sm"
              variant={mappingReviewed ? 'outline' : 'primary'}
              disabled={!reviewGate.hasCriticalMapping}
              onClick={() => {
                setMappingReviewed(true)
                toast.success('Critical mapping confirmed')
              }}
            >
              {mappingReviewed ? 'Mapping Confirmed' : 'Confirm Mapping Readiness'}
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <CardTitle className="!mb-1">Transaction Logic Preview</CardTitle>
            <p className="text-sm text-muted">
              This is how BSIE will draw money movement once your mapped columns become normalized transactions.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5 justify-end">
            <Badge variant={hasSignedAmount || hasDebitCredit ? 'blue' : 'gray'}>{amountModeLabel}</Badge>
            <Badge variant={hasCounterparty ? 'green' : 'gray'}>{counterpartyLabel}</Badge>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <FlowCard
            title="Transfer In"
            tone="green"
            left={<FlowNode icon={<Building2 size={16} />} label={hasCounterparty ? 'Other Bank / Account' : 'Other Bank / Unknown'} accent="green" />}
            middle={<ArrowRight size={16} className="text-success" />}
            right={<FlowNode icon={<Building2 size={16} />} label="Subject Bank / Account" accent="blue" />}
            detail={hasCounterparty
              ? 'Counterparty account/name flows into the subject account.'
              : 'Incoming money reaches the subject account, but the source side is still weak.'}
            rule={hasSignedAmount ? 'Positive signed amount -> IN' : 'Credit column -> IN'}
          />
          <FlowCard
            title="Transfer Out"
            tone="red"
            left={<FlowNode icon={<Building2 size={16} />} label="Subject Bank / Account" accent="blue" />}
            middle={<ArrowRight size={16} className="text-danger" />}
            right={<FlowNode icon={<Building2 size={16} />} label={hasCounterparty ? 'Other Bank / Account' : 'Other Bank / Unknown'} accent="red" />}
            detail={hasCounterparty
              ? 'Subject account sends money outward to the mapped counterparty side.'
              : 'Outgoing money leaves the subject account, but destination identity is still weak.'}
            rule={hasSignedAmount ? 'Negative signed amount -> OUT' : 'Debit column -> OUT'}
          />
          <FlowCard
            title="Deposit"
            tone="green"
            left={<FlowNode icon={<Wallet size={16} />} label="Cash / Money Source" accent="green" />}
            middle={<ArrowRight size={16} className="text-success" />}
            right={<FlowNode icon={<Building2 size={16} />} label="Subject Bank / Account" accent="blue" />}
            detail="If no real counterparty is present, an inbound money source is treated like deposit into the bank account."
            rule={hasSignedAmount ? 'Positive amount with no counterparty -> Deposit' : 'Credit without transfer identity -> Deposit'}
          />
          <FlowCard
            title="Withdraw"
            tone="red"
            left={<FlowNode icon={<Building2 size={16} />} label="Subject Bank / Account" accent="blue" />}
            middle={<ArrowRight size={16} className="text-danger" />}
            right={<FlowNode icon={<Wallet size={16} />} label="Cash / Money Out" accent="red" />}
            detail="If money leaves the bank without a real counterparty, BSIE maps it as withdrawal or cash-out."
            rule={hasSignedAmount ? 'Negative amount with no counterparty -> Withdraw' : 'Debit without transfer identity -> Withdraw'}
          />
        </div>

        <div className="mt-4 rounded-xl border border-border bg-surface2/60 px-4 py-3">
          <div className="flex items-center gap-2 mb-1 text-text2">
            <ArrowLeftRight size={14} className="text-accent" />
            <span className="text-sm font-semibold">Mapping Rule Summary</span>
          </div>
          <p className="text-xs text-muted leading-relaxed">
            Transfer logic prefers <span className="text-text2">bank/account to bank/account</span> when a counterparty account or name is mapped.
            Deposit and withdraw logic uses <span className="text-text2">money to bank</span> or <span className="text-text2">bank to money</span>
            when the counterparty side is absent and the row behaves like cash or system movement.
          </p>
        </div>
      </Card>

      {/* Mapping table */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <CardTitle className="!mb-0">Column Mapping</CardTitle>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={autoFill}>
              <Wand2 size={12} />Auto-fill
            </Button>
            <Button size="sm" variant="ghost" onClick={clearAll}>
              <X size={12} />Clear
            </Button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-[11px] uppercase text-muted font-semibold">Field</th>
                <th className="text-left py-2 px-3 text-[11px] uppercase text-muted font-semibold">Mapped to Column</th>
                <th className="text-left py-2 px-3 text-[11px] uppercase text-muted font-semibold">Confidence</th>
                <th className="text-left py-2 px-3 text-[11px] uppercase text-muted font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {FIELDS.map(({ key, label, required }) => {
                const val  = (confirmedMapping[key] as string) || ''
                const conf = Math.round(Number((confidenceScores[key] as number) || 0) * 100)
                const mapped = !!val
                return (
                  <tr key={key} className="border-b border-border/50 hover:bg-surface2/50 transition-colors">
                    <td className="py-2.5 px-3 font-medium text-text2">
                      {label}{required && <span className="text-danger ml-1">*</span>}
                    </td>
                    <td className="py-2.5 px-3">
                      <select
                        value={val}
                        onChange={e => update(key, e.target.value)}
                        className="bg-surface2 border border-border rounded-lg px-2 py-1 text-sm text-text w-full max-w-[220px] focus:border-accent outline-none cursor-pointer"
                      >
                        <option value="">— None —</option>
                        {allColumns.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-14 h-1.5 bg-surface3 rounded-full overflow-hidden">
                          <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${conf}%` }} />
                        </div>
                        <span className="text-xs text-muted w-8">{conf}%</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant={mapped ? 'green' : 'gray'}>{mapped ? 'Mapped' : 'Unmapped'}</Badge>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Sample data */}
      {sampleRows.length > 0 && (
        <Card>
          <CardTitle>Sample Data (first {sampleRows.length} rows)</CardTitle>
          <div className="overflow-x-auto max-h-44 rounded-lg border border-border">
            <table className="text-xs font-mono border-collapse w-full">
              <thead>
                <tr className="bg-surface2 sticky top-0">
                  {allColumns.map(c => (
                    <th key={c} className="py-1.5 px-2 text-left text-muted border border-border/50 truncate max-w-[120px] whitespace-nowrap">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sampleRows.map((row, i) => (
                  <tr key={i} className="hover:bg-surface2/40">
                    {allColumns.map(c => (
                      <td key={c} className="py-1 px-2 border border-border/30 truncate max-w-[120px] text-text2">
                        {String(row[c] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="flex gap-3">
        <Button variant="ghost" onClick={() => setStep(1)}>
          <ChevronLeft size={14} />Back
        </Button>
        <Button onClick={handleConfirm} disabled={saving || !canProceedToConfig}>
          {saving ? 'Saving…' : <><ChevronRight size={14} />Continue to Configure</>}
        </Button>
      </div>

      {/* Learn New Bank Modal */}
      {learnOpen && (
        <div className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4"
          onClick={() => setLearnOpen(false)}>
          <div className="bg-surface border border-border rounded-xl p-6 w-full max-w-[480px] shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-1">
              <BookPlus size={18} className="text-accent" />
              <h3 className="text-base font-bold text-text">Save as New Bank Template</h3>
            </div>
            <p className="text-xs text-muted mb-5">
              Your current column mappings will be saved as aliases for this bank.
              Next time a file from this bank is uploaded, it will be auto-detected.
            </p>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] uppercase text-muted font-semibold">Bank Key <span className="text-danger">*</span></label>
                  <input
                    value={learnForm.key}
                    onChange={e => setLearnForm(f => ({ ...f, key: e.target.value }))}
                    placeholder="e.g. mybank"
                    className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
                  />
                  <span className="text-[10px] text-muted">Lowercase, no spaces (used as filename)</span>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] uppercase text-muted font-semibold">Bank Name <span className="text-danger">*</span></label>
                  <input
                    value={learnForm.bank_name}
                    onChange={e => setLearnForm(f => ({ ...f, bank_name: e.target.value }))}
                    placeholder="e.g. My Bank"
                    className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] uppercase text-muted font-semibold">Format Type</label>
                  <select value={learnForm.format_type}
                    onChange={e => setLearnForm(f => ({ ...f, format_type: e.target.value }))}
                    className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none cursor-pointer">
                    <option value="standard">Standard (single amount)</option>
                    <option value="dual_account">Dual Account (debit + credit)</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] uppercase text-muted font-semibold">Amount Mode</label>
                  <select value={learnForm.amount_mode}
                    onChange={e => setLearnForm(f => ({ ...f, amount_mode: e.target.value }))}
                    className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none cursor-pointer">
                    <option value="signed">Signed (single +/- column)</option>
                    <option value="debit_credit">Debit / Credit columns</option>
                  </select>
                </div>
              </div>
              <div className="bg-surface2 rounded-lg p-3 border border-border/50">
                <div className="text-[11px] uppercase text-muted font-semibold mb-2">Mappings to save</div>
                <div className="flex flex-wrap gap-1.5">
                  {FIELDS.filter(f => confirmedMapping[f.key]).map(f => (
                    <span key={f.key} className="text-[11px] bg-accent/10 text-accent px-2 py-0.5 rounded-full">
                      {f.label} → {confirmedMapping[f.key]}
                    </span>
                  ))}
                  {!Object.values(confirmedMapping).some(Boolean) && (
                    <span className="text-xs text-warning">No fields mapped yet — map columns above first</span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <Button variant="ghost" onClick={() => setLearnOpen(false)}>Cancel</Button>
              <Button variant="primary" onClick={handleLearn} disabled={learning}>
                {learning ? 'Saving…' : <><BookPlus size={13} />Save Bank Template</>}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function formatEvidenceItem(value: string) {
  return String(value || '')
    .replace(/->/g, ' -> ')
    .replace(/_/g, ' ')
    .replace(/:/g, ': ')
    .replace(/\s+/g, ' ')
    .trim()
}

function FlowCard({
  title,
  tone,
  left,
  middle,
  right,
  detail,
  rule,
}: {
  title: string
  tone: 'green' | 'red'
  left: React.ReactNode
  middle: React.ReactNode
  right: React.ReactNode
  detail: string
  rule: string
}) {
  const toneClasses = tone === 'green'
    ? 'border-success/25 bg-success/[0.05]'
    : 'border-danger/25 bg-danger/[0.05]'

  return (
    <div className={`rounded-xl border p-4 ${toneClasses}`}>
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="text-sm font-semibold text-text">{title}</div>
        <Badge variant={tone === 'green' ? 'green' : 'red'}>{tone === 'green' ? 'IN Logic' : 'OUT Logic'}</Badge>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
        {left}
        <div className="flex items-center justify-center">{middle}</div>
        {right}
      </div>
      <div className="mt-3 pt-3 border-t border-border/60 space-y-1">
        <div className="text-[11px] uppercase text-muted font-semibold">Rule</div>
        <div className="text-xs text-text2">{rule}</div>
        <div className="text-xs text-muted leading-relaxed">{detail}</div>
      </div>
    </div>
  )
}

function FlowNode({
  icon,
  label,
  accent,
}: {
  icon: React.ReactNode
  label: string
  accent: 'blue' | 'green' | 'red'
}) {
  const accentClasses = {
    blue: 'border-accent/30 bg-accent/10 text-accent',
    green: 'border-success/30 bg-success/10 text-success',
    red: 'border-danger/30 bg-danger/10 text-danger',
  }

  return (
    <div className="rounded-xl border border-border/60 bg-surface px-3 py-3 min-h-[84px] flex flex-col justify-center">
      <div className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-semibold ${accentClasses[accent]}`}>
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted">
        <CircleDashed size={12} />
        <span>mapping state preview</span>
      </div>
    </div>
  )
}
