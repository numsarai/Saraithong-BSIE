import { useEffect, useState } from 'react'
import { normalizeOperatorName, useStore } from '@/store'
import { getBanks, lookupRememberedAccountName, startProcess } from '@/api'
import { BankLogo } from '@/components/BankLogo'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { toast } from 'sonner'
import { ChevronLeft, Play } from 'lucide-react'

export function Step3Config() {
  const {
    bankKey, account, name, setBankKey, setAccount, setName,
    banks, setBanks, tempFilePath, fileId, headerRow, sheetName, confirmedMapping, setJobId, setParserRunId, setStep, operatorName,
  } = useStore()
  const [loading, setLoading] = useState(false)
  const [rememberedName, setRememberedName] = useState('')
  const [checkingRememberedName, setCheckingRememberedName] = useState(false)
  const selectedBank = banks.find((bank: any) => bank.key === bankKey) || null

  useEffect(() => {
    getBanks().then(setBanks).catch(() => toast.error('Could not load bank list'))
  }, [setBanks])

  useEffect(() => {
    const safeAccount = account.replace(/\D/g, '')
    if (!safeAccount.match(/^\d{10}$|^\d{12}$/)) {
      setRememberedName('')
      setCheckingRememberedName(false)
      return
    }

    let cancelled = false
    setCheckingRememberedName(true)
    setRememberedName('')

    lookupRememberedAccountName({ account: safeAccount, bank_key: bankKey })
      .then((data) => {
        if (cancelled) return
        const nextRememberedName = String(data.remembered_name || '').trim()
        setRememberedName(nextRememberedName)
        if (nextRememberedName && !useStore.getState().name.trim()) {
          setName(nextRememberedName)
        }
      })
      .catch(() => {
        if (cancelled) return
        setRememberedName('')
      })
      .finally(() => {
        if (!cancelled) setCheckingRememberedName(false)
      })

    return () => {
      cancelled = true
    }
  }, [account, bankKey, setName])

  const handleRun = async () => {
    if (!account.match(/^\d{10}$|^\d{12}$/)) {
      toast.error('Account number must be exactly 10 or 12 digits')
      return
    }
    if (!name.trim()) { toast.error('Account holder name is required'); return }
    setLoading(true)
    try {
      if (!tempFilePath) { toast.error('No file uploaded — go back to step 1'); return }
      const data = await startProcess({
        temp_file_path: tempFilePath,
        file_id: fileId,
        bank_key: bankKey,
        account,
        name,
        confirmed_mapping: confirmedMapping,
        operator: normalizeOperatorName(operatorName),
        header_row: headerRow,
        sheet_name: sheetName,
      })
      setJobId(data.job_id)
      setParserRunId(data.parser_run_id || null)
      setStep(4)
    } catch (e: any) {
      toast.error(`Failed to start: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg space-y-5">
      <div>
        <h2 className="text-lg font-bold mb-1 text-text">Configure Pipeline</h2>
        <p className="text-muted text-sm">Set the subject account details before running.</p>
      </div>

      <Card>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2 flex flex-col gap-1.5">
            <label className="text-[11px] uppercase text-muted font-semibold">Bank</label>
            <div className="mb-2 flex items-center gap-3 rounded-xl border border-border/70 bg-surface2/50 px-3 py-2">
              <BankLogo bank={selectedBank || { key: bankKey, name: bankKey || 'Unknown bank' }} size="md" />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-text">{selectedBank?.name || bankKey || 'Unknown bank'}</div>
                <div className="text-xs text-muted">Selected bank template for pipeline normalization</div>
              </div>
            </div>
            <select
              value={bankKey}
              onChange={e => setBankKey(e.target.value)}
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none cursor-pointer"
            >
              {banks.map((b: any) => <option key={b.key} value={b.key}>{b.name}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] uppercase text-muted font-semibold">
              Account Number <span className="text-danger">*</span>
            </label>
            <input
              value={account}
              onChange={e => setAccount(e.target.value.replace(/\D/g, ''))}
              placeholder="10 or 12 digits"
              maxLength={12}
              inputMode="numeric"
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
            />
            <span className="text-[11px] text-muted">Digits only, exactly 10 or 12</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] uppercase text-muted font-semibold">
              Account Holder Name <span className="text-danger">*</span>
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Full name"
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
            />
          </div>
          {(checkingRememberedName || rememberedName) ? (
            <div className="col-span-2 rounded-lg border border-border bg-surface2/70 px-3 py-2 text-xs text-muted">
              {checkingRememberedName
                ? 'Checking remembered account name from previous imports…'
                : (
                  <>
                    Remembered from previous imports: <span className="font-semibold text-text">{rememberedName}</span>. You can edit this before running.
                  </>
                )}
            </div>
          ) : null}
        </div>
      </Card>

      <div className="flex gap-3">
        <Button variant="ghost" onClick={() => setStep(2)}>
          <ChevronLeft size={14} />Back
        </Button>
        <Button variant="success" onClick={handleRun} disabled={loading}>
          {loading ? 'Starting…' : <><Play size={14} />Run Pipeline</>}
        </Button>
      </div>
    </div>
  )
}
