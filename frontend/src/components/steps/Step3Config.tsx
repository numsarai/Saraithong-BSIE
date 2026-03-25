import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import { getBanks, startProcess } from '@/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { toast } from 'sonner'
import { ChevronLeft, Play } from 'lucide-react'

export function Step3Config() {
  const {
    bankKey, account, name, setBankKey, setAccount, setName,
    banks, setBanks, tempFilePath, confirmedMapping, setJobId, setStep,
  } = useStore()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getBanks().then(setBanks).catch(() => toast.error('Could not load bank list'))
  }, [setBanks])

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
        bank_key: bankKey,
        account,
        name,
        confirmed_mapping: confirmedMapping,
      })
      setJobId(data.job_id)
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
