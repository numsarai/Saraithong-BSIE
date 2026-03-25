import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import { confirmMapping, getBanks, learnBank } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardTitle } from '@/components/ui/card'
import { toast } from 'sonner'
import { ChevronLeft, ChevronRight, Wand2, X, BookPlus } from 'lucide-react'

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

  const update = (field: string, value: string) =>
    setConfirmedMapping({ ...confirmedMapping, [field]: value || null })

  const autoFill = () => setConfirmedMapping({ ...suggestedMapping })
  const clearAll = () => {
    const cleared: Record<string, null> = {}
    FIELDS.forEach(f => { cleared[f.key] = null })
    setConfirmedMapping(cleared)
  }

  const handleConfirm = async () => {
    if (!confirmedMapping['date'])        { toast.error('Date field is required'); return }
    if (!confirmedMapping['description']) { toast.error('Description field is required'); return }
    setSaving(true)
    try {
      await confirmMapping(bankKey, confirmedMapping, allColumns)
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
  const confidence  = Math.round((detectedBank?.score || 0) * 100)

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
                const conf = (confidenceScores[key] as number) || 0
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
        <Button onClick={handleConfirm} disabled={saving}>
          {saving ? 'Saving…' : <><ChevronRight size={14} />Confirm Mapping</>}
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
