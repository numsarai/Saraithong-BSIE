import { useEffect, useState } from 'react'
import { normalizeOperatorName, useStore } from '@/store'
import { getBanks, lookupRememberedAccountName, startProcess } from '@/api'
import { BankLogo } from '@/components/BankLogo'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { toast } from 'sonner'
import { ChevronLeft, Play } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export function Step3Config() {
  const { t } = useTranslation()
  const {
    bankKey, account, name, setBankKey, setAccount, setName,
    banks, setBanks, tempFilePath, fileId, headerRow, sheetName, confirmedMapping, setJobId, setParserRunId, setStep, operatorName, identityGuess,
  } = useStore()
  const [loading, setLoading] = useState(false)
  const [rememberedName, setRememberedName] = useState('')
  const [checkingRememberedName, setCheckingRememberedName] = useState(false)
  const selectedBank = banks.find((bank: any) => bank.key === bankKey) || null
  const guessedAccount = String(identityGuess?.account || '').trim()
  const guessedName = String(identityGuess?.name || '').trim()
  const accountGuessSource = formatIdentitySource(identityGuess?.account_source, t)
  const nameGuessSource = formatIdentitySource(identityGuess?.name_source, t)

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
        <h2 className="text-lg font-bold mb-1 text-text">{t('step3.title')}</h2>
        <p className="text-muted text-sm">{t('step3.description')}</p>
      </div>

      <Card>
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2 flex flex-col gap-1.5">
            <label className="text-[11px] uppercase text-muted font-semibold">{t('step3.bank')}</label>
            <div className="mb-2 flex items-center gap-3 rounded-xl border border-border/70 bg-surface2/50 px-3 py-2">
              <BankLogo bank={selectedBank || { key: bankKey, name: bankKey || 'Unknown bank' }} size="md" />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-text">{selectedBank?.name || bankKey || 'Unknown bank'}</div>
                <div className="text-xs text-muted">{t('step3.selectedBankTemplate')}</div>
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
              {t('step3.accountNumber')} <span className="text-danger">*</span>
            </label>
            <input
              value={account}
              onChange={e => setAccount(e.target.value.replace(/\D/g, ''))}
              placeholder={t('step3.accountPlaceholder')}
              maxLength={12}
              inputMode="numeric"
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
            />
            <span className="text-[11px] text-muted">{t('step3.accountHint')}</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] uppercase text-muted font-semibold">
              {t('step3.accountHolderName')} <span className="text-danger">*</span>
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder={t('step3.namePlaceholder')}
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
            />
          </div>
          {(guessedAccount || guessedName) ? (
            <div className="col-span-2 rounded-lg border border-accent/25 bg-accent/[0.06] px-3 py-2 text-xs text-muted">
              <span className="font-semibold text-text">{t('step3.detectedFromStatement')}</span>{' '}
              {guessedAccount
                ? <>{t('step3.account')} <span className="font-mono text-text">{guessedAccount}</span>{accountGuessSource ? ` ${t('step3.via')} ${accountGuessSource}` : ''}.</>
                : null}{' '}
              {guessedName
                ? <>{t('step3.name')} <span className="font-semibold text-text">{guessedName}</span>{nameGuessSource ? ` ${t('step3.via')} ${nameGuessSource}` : ''}.</>
                : null}
            </div>
          ) : null}
          {(checkingRememberedName || rememberedName) ? (
            <div className="col-span-2 rounded-lg border border-border bg-surface2/70 px-3 py-2 text-xs text-muted">
              {checkingRememberedName
                ? t('step3.checkingRememberedName')
                : (
                  <>
                    {t('step3.rememberedName')} <span className="font-semibold text-text">{rememberedName}</span>. {t('step3.rememberedNameHint')}
                  </>
                )}
            </div>
          ) : null}
        </div>
      </Card>

      <div className="flex gap-3">
        <Button variant="ghost" onClick={() => setStep(2)}>
          <ChevronLeft size={14} />{t('step3.back')}
        </Button>
        <Button variant="success" onClick={handleRun} disabled={loading}>
          {loading ? t('step3.starting') : <><Play size={14} />{t('step3.runPipeline')}</>}
        </Button>
      </div>
    </div>
  )
}

function formatIdentitySource(value: unknown, t: (key: string) => string) {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return ''
  if (normalized === 'filename') return t('step3.identitySource.filename')
  if (normalized === 'workbook_header') return t('step3.identitySource.workbookHeader')
  if (normalized === 'transaction_pattern') return t('step3.identitySource.repeatedPattern')
  if (normalized === 'ofx_account_block') return t('step3.identitySource.ofxBlock')
  return normalized.replace(/_/g, ' ')
}
