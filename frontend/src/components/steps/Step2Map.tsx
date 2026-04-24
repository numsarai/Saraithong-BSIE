import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { normalizeOperatorName, useStore } from '@/store'
import { assistMapping, assistVisionMapping, confirmMapping, getBanks, learnBank, previewMapping, verifyAccountPresence } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardTitle } from '@/components/ui/card'
import { BankLogo } from '@/components/BankLogo'
import { evaluateReviewGate } from '@/lib/reviewGate'
import { toast } from 'sonner'
import { ChevronLeft, ChevronRight, Wand2, X, BookPlus, ArrowRight, ArrowLeftRight, Building2, Wallet, CircleDashed, FileSearch, BrainCircuit, DatabaseZap, ShieldAlert, ShieldCheck, Sparkles, Loader2 } from 'lucide-react'

export function Step2Map() {
  const { t } = useTranslation()

  const FIELDS = [
    { key: 'date',                 label: t('step2.fields.date'),               required: true  },
    { key: 'time',                 label: t('step2.fields.time'),               required: false },
    { key: 'description',          label: t('step2.fields.description'),        required: true  },
    { key: 'amount',               label: t('step2.fields.amount'),             required: false },
    { key: 'direction_marker',     label: t('step2.fields.directionMarker'),    required: false },
    { key: 'debit',                label: t('step2.fields.debit'),              required: false },
    { key: 'credit',               label: t('step2.fields.credit'),             required: false },
    { key: 'balance',              label: t('step2.fields.balance'),            required: false },
    { key: 'channel',              label: t('step2.fields.channel'),            required: false },
    { key: 'counterparty_account', label: t('step2.fields.counterpartyAccount'), required: false },
    { key: 'counterparty_name',    label: t('step2.fields.counterpartyName'),   required: false },
  ]
  const {
    detectedBank, allColumns, suggestedMapping, confirmedMapping,
    setConfirmedMapping, sampleRows, bankKey, setBankKey, setStep, confidenceScores,
    headerRow, sheetName, memoryMatch, bankMemoryMatch, templateVariantMatch, suggestionSource,
    bankReviewed, accountReviewed, mappingReviewed, setBankReviewed, setAccountReviewed, setMappingReviewed,
    isBlockedCase, canProceedToConfig, operatorName, fileId, fileName,
    account, name, setAccount, setName, identityGuess,
  } = useStore()
  const [saving, setSaving]         = useState(false)
  const [banks, setBanks]           = useState<any[]>([])
  const [learnOpen, setLearnOpen]   = useState(false)
  const [learnForm, setLearnForm]   = useState({
    key: '', bank_name: '', format_type: 'standard', amount_mode: 'signed',
  })
  const [learning, setLearning]     = useState(false)
  const [serverPreview, setServerPreview] = useState<any | null>(null)
  const [assistLoading, setAssistLoading] = useState(false)
  const [mappingAssist, setMappingAssist] = useState<any | null>(null)
  const [presenceLoading, setPresenceLoading] = useState(false)
  const [accountPresence, setAccountPresence] = useState<any | null>(null)

  useEffect(() => {
    getBanks().then(setBanks).catch((e) => toast.error(`Could not load banks: ${e.message}`))
  }, [])

  const update = (field: string, value: string) => {
    const nextMapping = { ...confirmedMapping, [field]: value || null }
    const criticalField = field === 'date' || field === 'description' || field === 'amount' || field === 'direction_marker' || field === 'debit' || field === 'credit'
    if (criticalField && mappingReviewed) {
      setMappingReviewed(false)
    }
    setServerPreview(null)
    setMappingAssist(null)
    setConfirmedMapping(nextMapping)
  }

  const autoFill = () => {
    if (mappingReviewed) {
      setMappingReviewed(false)
    }
    setServerPreview(null)
    setMappingAssist(null)
    setConfirmedMapping({ ...suggestedMapping })
  }
  const clearAll = () => {
    const cleared: Record<string, null> = {}
    FIELDS.forEach(f => { cleared[f.key] = null })
    if (mappingReviewed) {
      setMappingReviewed(false)
    }
    setServerPreview(null)
    setMappingAssist(null)
    setConfirmedMapping(cleared)
  }

  const handleMappingAssist = async () => {
    if (!allColumns.length) {
      toast.error(t('step2.assist.noColumns'))
      return
    }
    setAssistLoading(true)
    try {
      const result = await assistMapping({
        bank: bankKey,
        detected_bank: detectedBank,
        columns: allColumns,
        sample_rows: sampleRows,
        current_mapping: confirmedMapping,
        subject_account: account,
        subject_name: name,
        identity_guess: identityGuess,
        account_presence: accountPresence,
        sheet_name: sheetName,
        header_row: headerRow,
      })
      setMappingAssist(result)
      toast.success(t('step2.assist.ready'))
    } catch (e: any) {
      toast.error(`${t('step2.assist.failed')}: ${e.message}`)
    } finally {
      setAssistLoading(false)
    }
  }

  const handleVisionMappingAssist = async () => {
    if (!allColumns.length) {
      toast.error(t('step2.assist.noColumns'))
      return
    }
    if (!fileId) {
      toast.error(t('step2.assist.noFile'))
      return
    }
    setAssistLoading(true)
    try {
      const result = await assistVisionMapping({
        file_id: fileId,
        bank: bankKey,
        detected_bank: detectedBank,
        columns: allColumns,
        sample_rows: sampleRows,
        current_mapping: confirmedMapping,
        subject_account: account,
        subject_name: name,
        identity_guess: identityGuess,
        account_presence: accountPresence,
        sheet_name: sheetName,
        header_row: headerRow,
      })
      setMappingAssist(result)
      toast.success(t('step2.assist.ready'))
    } catch (e: any) {
      toast.error(`${t('step2.assist.failed')}: ${e.message}`)
    } finally {
      setAssistLoading(false)
    }
  }

  const applyMappingAssist = () => {
    if (!mappingAssist?.mapping) return
    if (mappingReviewed) {
      setMappingReviewed(false)
    }
    setServerPreview(null)
    setConfirmedMapping(mappingAssist.mapping)
    toast.success(t('step2.assist.applied'))
  }

  const handleVerifyAccountPresence = async () => {
    const safeAccount = account.replace(/\D/g, '')
    if (!safeAccount.match(/^\d{10}$|^\d{12}$/)) {
      toast.error('Account number must be exactly 10 or 12 digits')
      return
    }
    if (!fileId) {
      toast.error('No stored evidence file is available for account verification')
      return
    }
    setPresenceLoading(true)
    try {
      const result = await verifyAccountPresence({
        file_id: fileId,
        subject_account: safeAccount,
        sheet_name: sheetName,
        header_row: headerRow,
        max_matches: 25,
      })
      setAccountPresence(result)
      if (result?.found) {
        toast.success('Account found in workbook evidence')
      } else if (result?.possible_match) {
        toast.success('Possible account match found; review leading-zero warning')
      } else {
        toast.error(result?.warnings?.[0] || 'Account was not found in workbook evidence')
      }
    } catch (e: any) {
      toast.error(`Account verification failed: ${e.message}`)
    } finally {
      setPresenceLoading(false)
    }
  }

  const handleConfirm = async () => {
    if (!canProceedToConfig) {
      toast.error('Resolve the analyst review gate before continuing')
      return
    }
    if (!confirmedMapping['date'])        { toast.error('Date field is required'); return }
    if (!confirmedMapping['description']) { toast.error('Description field is required'); return }
    if (mappingValidation.errors.length > 0) {
      toast.error(mappingValidation.errors[0].message)
      return
    }
    setSaving(true)
    try {
      const preview = await previewMapping({
        bank: bankKey,
        mapping: confirmedMapping,
        columns: allColumns,
        sample_rows: sampleRows,
      })
      setServerPreview(preview)
      if (!preview?.ok) {
        const message = preview?.errors?.[0]?.message || 'Mapping preview failed'
        toast.error(message)
        return
      }
      const response = await confirmMapping(
        bankKey,
        confirmedMapping,
        allColumns,
        headerRow,
        sheetName,
        {
          reviewer: normalizeOperatorName(operatorName),
          detected_bank: detectedBank,
          suggested_mapping: suggestedMapping,
          subject_account: account,
          subject_name: name,
          identity_guess: identityGuess,
          account_presence: accountPresence,
          sample_rows: sampleRows,
          promote_shared: false,
        },
      )
      setStep(3)
      const feedbackMode = String(
        response?.feedback_mode
        || response?.feedback_type
        || response?.feedback_action
        || response?.learning_signal
        || '',
      ).toLowerCase()
      const feedbackMessage = String(response?.message || response?.detail || '').trim()
      const successMessage = feedbackMessage || (
        feedbackMode.includes('correct')
          ? 'Saved as a correction'
          : feedbackMode.includes('confirm')
            ? 'Saved and reinforced'
            : 'Mapping saved'
      )
      toast.success(successMessage)
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
  const mappingValidation = useMemo(
    () => evaluateLocalMapping(confirmedMapping, allColumns),
    [confirmedMapping, allColumns],
  )
  const hasBlockingMappingErrors = mappingValidation.errors.length > 0
  const reviewGate = evaluateReviewGate({
    detectedBank,
    selectedBankKey: bankKey,
    selectedAccount: account,
    inferredAccount: identityGuess?.account,
    mapping: confirmedMapping,
    bankReviewed,
    accountReviewed,
    mappingReviewed,
  })
  const confidence  = reviewGate.confidencePercent
  const hasSignedAmount = !!confirmedMapping['amount']
  const hasDirectionMarker = !!confirmedMapping['direction_marker']
  const hasDirectionMarkerAmount = hasSignedAmount && hasDirectionMarker
  const hasDebitCredit = !!confirmedMapping['debit'] || !!confirmedMapping['credit']
  const hasCounterparty = !!confirmedMapping['counterparty_account'] || !!confirmedMapping['counterparty_name']
  const amountModeLabel = hasDirectionMarkerAmount ? 'Direction Marker Mode' : hasSignedAmount ? 'Signed Amount Mode' : hasDebitCredit ? 'Debit / Credit Mode' : 'Amount Not Mapped'
  const inboundAmountRule = hasDirectionMarkerAmount ? 'CR / IN marker -> IN' : hasSignedAmount ? 'Positive signed amount -> IN' : 'Credit column -> IN'
  const outboundAmountRule = hasDirectionMarkerAmount ? 'DR / OUT marker -> OUT' : hasSignedAmount ? 'Negative signed amount -> OUT' : 'Debit column -> OUT'
  const counterpartyLabel = hasCounterparty ? 'Counterparty mapped' : 'Counterparty not mapped yet'
  const candidateKeys = Array.isArray(detectedBank?.top_candidates) ? detectedBank.top_candidates : []
  const selectedBank = banks.find((bank: any) => bank.key === bankKey) || null
  const detectedBankKey = String(detectedBank?.key || detectedBank?.config_key || '').trim().toLowerCase()
  const detectedBankEntry = banks.find((bank: any) => bank.key === detectedBankKey) || null
  const bankOverrideDetected = reviewGate.bankOverrideDetected
  const selectedAccount = normalizeAccount(account)
  const inferredAccount = normalizeAccount(identityGuess?.account)
  const accountMismatchDetected = reviewGate.accountMismatchDetected
  const accountContextStatus = accountMismatchDetected
    ? 'Manual override'
    : selectedAccount && inferredAccount
      ? 'Matches statement'
      : selectedAccount
        ? 'Analyst provided'
        : inferredAccount
          ? 'Detected only'
          : 'Not provided'
  const presenceStatus = String(accountPresence?.match_status || '').replace(/_/g, ' ')
  const presenceBadgeVariant: 'blue' | 'green' | 'red' | 'gray' = accountPresence?.found ? 'green' : accountPresence?.possible_match ? 'blue' : accountPresence ? 'red' : 'gray'
  const rankedCandidates = candidateKeys.map((key: string) => ({
    key,
    name: banks.find((bank: any) => bank.key === key)?.name || key.toUpperCase(),
    logo_url: banks.find((bank: any) => bank.key === key)?.logo_url || `/api/bank-logos/${key}.svg`,
    score: Number(detectedBank?.scores?.[key] || 0),
    selected: key === bankKey,
  }))
  const positiveEvidence = Array.isArray(detectedBank?.evidence?.positive) ? detectedBank.evidence.positive.slice(0, 6) : []
  const negativeEvidence = Array.isArray(detectedBank?.evidence?.negative) ? detectedBank.evidence.negative.slice(0, 4) : []
  const suggestionSourceLabel = formatEvidenceItem(suggestionSource || 'auto')
  const templateVariantScore = Math.round(Number(templateVariantMatch?.match_score || 0) * 100)
  const templateVariantTrust = formatEvidenceItem(templateVariantMatch?.trust_state || '')
  const isVisionAssistAvailable = !!fileId && /\.(pdf|png|jpe?g|bmp)$/i.test(String(fileName || ''))

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h2 className="text-lg font-bold mb-1 text-text">{t('step2.title')}</h2>
        <p className="text-muted text-sm">{t('step2.description')}</p>
      </div>

      {/* Detection summary + Manual Bank Select */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="!p-4 col-span-1">
          <div className="text-[11px] uppercase text-muted mb-2 font-semibold">{t('step2.bank')}</div>
          <div className="mb-3 flex items-center gap-3 rounded-xl border border-border/70 bg-surface2/50 px-3 py-2">
            <BankLogo bank={selectedBank || { key: bankKey, name: detectedBank?.bank || bankKey }} size="md" />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-text">{selectedBank?.name || detectedBank?.bank || bankKey || 'Unknown bank'}</div>
              <div className="text-xs text-muted">{t('step2.selectedTemplate')}</div>
            </div>
          </div>
          <select
            value={bankKey}
            onChange={e => {
              setServerPreview(null)
              setBankKey(e.target.value)
            }}
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
          <div className="text-[11px] uppercase text-muted mb-1 font-semibold">{t('step2.columnsFound')}</div>
          <div className="text-lg font-bold text-text">{allColumns.length}</div>
          <div className="text-xs text-muted mt-1">{mappedCount} of {FIELDS.length} {t('step2.fieldsMapped')}</div>
        </Card>
        <Card className="!p-4 flex flex-col justify-between">
          <div>
            <div className="text-[11px] uppercase text-muted mb-1 font-semibold">{t('step2.newBank')}</div>
            <div className="text-xs text-muted">{t('step2.newBankHint')}</div>
          </div>
          <Button size="sm" variant="outline" className="mt-3" onClick={() => {
            setLearnForm({ key: '', bank_name: '', format_type: 'standard', amount_mode: 'signed' })
            setLearnOpen(true)
          }}>
            <BookPlus size={13} />{t('step2.learnNewBank')}
          </Button>
        </Card>
      </div>

      <Card>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <CardTitle className="!mb-1">{t('step2.detectionReview')}</CardTitle>
            <p className="text-sm text-muted">
              Analyst view of the sheet/header chosen, ranked bank candidates, and the evidence used for auto-detection.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5 justify-end">
            <Badge variant="gray">{t('step2.sheet')}: {sheetName || t('step2.unknown')}</Badge>
            <Badge variant="gray">{t('step2.headerRow')}: {headerRow + 1}</Badge>
            <Badge variant={suggestionSource === 'template_variant' ? 'green' : suggestionSource === 'mapping_profile' ? 'blue' : 'gray'}>
              Suggestion: {suggestionSourceLabel}
            </Badge>
            <Badge variant={detectedBank?.ambiguous ? 'red' : confidence >= 75 ? 'green' : 'blue'}>
              {detectedBank?.ambiguous ? t('step2.analystReviewNeeded') : t('step2.detectionStable')}
            </Badge>
          </div>
        </div>

        {bankOverrideDetected && (
          <div className="mb-4 rounded-xl border border-warning/30 bg-warning/10 p-4">
            <div className="flex items-center gap-2 text-text2 mb-1">
              <ShieldAlert size={16} className="text-warning" />
              <span className="text-sm font-semibold">Selected bank overrides auto-detection</span>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              BSIE detected {detectedBankEntry?.name || detectedBank?.bank || detectedBankKey.toUpperCase()}, but this run will use {selectedBank?.name || bankKey.toUpperCase()} after analyst confirmation.
            </p>
          </div>
        )}

        <div className={`mb-4 rounded-xl border p-4 ${accountMismatchDetected ? 'border-warning/30 bg-warning/10' : 'border-border bg-surface2/50'}`}>
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <div className="flex items-center gap-2 text-text2">
                <Wallet size={15} className={accountMismatchDetected ? 'text-warning' : 'text-accent'} />
                <span className="text-sm font-semibold">Known Account Context</span>
              </div>
              <p className="mt-1 text-xs text-muted leading-relaxed">
                Use the account from the legal request as analyst context before asking mapping assist or confirming the layout.
              </p>
            </div>
            <Badge variant={accountMismatchDetected ? 'red' : selectedAccount ? 'green' : 'gray'}>{accountContextStatus}</Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-[11px] uppercase text-muted font-semibold">Known account number</span>
              <input
                value={account}
                onChange={e => {
                  setServerPreview(null)
                  setMappingAssist(null)
                  setAccountPresence(null)
                  setAccount(e.target.value.replace(/\D/g, '').slice(0, 12))
                }}
                placeholder="10 or 12 digits"
                maxLength={12}
                inputMode="numeric"
                className="bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-[11px] uppercase text-muted font-semibold">Known account holder</span>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Account holder name"
                className="bg-surface border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
              />
            </label>
          </div>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg border border-border/70 bg-surface px-3 py-2">
              <span className="text-muted">Statement-inferred account: </span>
              <span className="font-mono text-text">{inferredAccount || 'not detected'}</span>
            </div>
            <div className="rounded-lg border border-border/70 bg-surface px-3 py-2">
              <span className="text-muted">Inference source: </span>
              <span className="text-text">{formatEvidenceItem(identityGuess?.account_source || 'none')}</span>
            </div>
          </div>
          <div className="mt-3 rounded-lg border border-border/70 bg-surface px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Badge variant={presenceBadgeVariant}>
                  {accountPresence ? presenceStatus || 'checked' : 'Not checked'}
                </Badge>
                <span className="text-xs text-muted">
                  {accountPresence
                    ? `${accountPresence.summary?.exact_match_count || 0} exact, ${accountPresence.summary?.possible_match_count || 0} possible`
                    : 'Scan the selected workbook sheet before pipeline processing.'}
                </span>
              </div>
              <Button
                size="sm"
                variant="outline"
                disabled={presenceLoading || !selectedAccount || !fileId}
                onClick={handleVerifyAccountPresence}
              >
                {presenceLoading ? <Loader2 size={13} className="animate-spin" /> : <FileSearch size={13} />}
                {presenceLoading ? 'Verifying' : 'Verify in Workbook'}
              </Button>
            </div>
            {accountPresence?.locations?.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {accountPresence.locations.slice(0, 4).map((location: any) => (
                  <span key={`${location.sheet_name}:${location.row_number}:${location.column_number}`} className="rounded-full border border-success/20 bg-success/10 px-2 py-1 text-[11px] text-success">
                    {location.sheet_name} R{location.row_number}C{location.column_number} {location.column_label ? `(${location.column_label})` : ''}
                  </span>
                ))}
              </div>
            )}
            {accountPresence?.warnings?.length > 0 && (
              <div className="mt-2 text-xs text-muted leading-relaxed">{accountPresence.warnings[0]}</div>
            )}
          </div>
          {accountMismatchDetected && (
            <div className="mt-3 text-xs text-muted leading-relaxed">
              BSIE inferred <span className="font-mono text-text">{inferredAccount}</span>, but this run will use <span className="font-mono text-text">{selectedAccount}</span> after analyst confirmation.
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-xl border border-border bg-surface2/50 p-4">
            <div className="flex items-center gap-2 mb-3 text-text2">
              <FileSearch size={14} className="text-accent" />
              <span className="text-sm font-semibold">{t('step2.workbookContext')}</span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted">{t('step2.detectedBank')}</span>
                <span className="flex items-center gap-2 font-medium text-text">
                  <BankLogo bank={detectedBankEntry || { key: detectedBankKey, name: detectedBank?.bank || 'UNKNOWN' }} size="sm" />
                  <span>{detectedBank?.bank || 'UNKNOWN'}</span>
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted">{t('step2.confidence')}</span>
                <span className="font-medium text-text">{confidence}%</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted">{t('step2.observedLayout')}</span>
                <span className="font-medium text-text">{formatEvidenceItem(detectedBank?.evidence?.layout || 'unknown')}</span>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {bankMemoryMatch && (
                <div className="rounded-lg border border-success/25 bg-success/[0.06] p-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-text2">
                    <BrainCircuit size={13} className="text-success" />
                    <span>{t('step2.bankFingerprintMatched')}</span>
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
                    <span>{t('step2.columnMappingMemoryMatched')}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    Profile {memoryMatch.profile_id} reused from {memoryMatch.bank} ({memoryMatch.usage_count} prior uses)
                  </div>
                </div>
              )}
              {templateVariantMatch && (
                <div className="rounded-lg border border-success/25 bg-success/[0.06] p-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-text2">
                    <ShieldCheck size={13} className="text-success" />
                    <span>Template variant matched</span>
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {templateVariantMatch.bank_key} {templateVariantTrust} via {formatEvidenceItem(templateVariantMatch.match_type || 'memory')} ({templateVariantScore}%)
                  </div>
                  <div className="mt-1 text-[11px] text-muted">
                    {Number(templateVariantMatch.confirmation_count || 0)} confirmations from {Number(templateVariantMatch.reviewer_count || 0)} reviewer(s); analyst confirmation still applies.
                  </div>
                </div>
              )}
              {!bankMemoryMatch && !memoryMatch && !templateVariantMatch && (
                <div className="rounded-lg border border-border/70 bg-surface p-3 text-xs text-muted">
                  {t('step2.noMemoryHit')}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-surface2/50 p-4">
            <div className="flex items-center gap-2 mb-3 text-text2">
              <ArrowLeftRight size={14} className="text-accent" />
              <span className="text-sm font-semibold">{t('step2.topCandidates')}</span>
            </div>
            <div className="space-y-2">
              {rankedCandidates.map((candidate: { key: string; name: string; logo_url: string; score: number; selected: boolean }) => (
                <div key={candidate.key} className={`rounded-lg border px-3 py-2 ${candidate.selected ? 'border-accent/40 bg-accent/[0.06]' : 'border-border/70 bg-surface'}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <BankLogo bank={candidate} size="sm" />
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

        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-border bg-surface2/50 p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <div className="text-sm font-semibold text-text">Confirm Selected Bank</div>
                <div className="text-xs text-muted">Required when detection is ambiguous, below 75% confidence, or manually overridden.</div>
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
                <div className="text-sm font-semibold text-text">Confirm Known Account</div>
                <div className="text-xs text-muted">Required when analyst account conflicts with statement inference.</div>
              </div>
              <Badge variant={accountReviewed ? 'green' : reviewGate.accountNeedsReview ? 'red' : 'gray'}>
                {accountReviewed ? 'Confirmed' : reviewGate.accountNeedsReview ? 'Required' : 'Auto-cleared'}
              </Badge>
            </div>
            <Button
              size="sm"
              variant={accountReviewed ? 'outline' : 'primary'}
              disabled={!reviewGate.accountNeedsReview || !selectedAccount}
              onClick={() => {
                setAccountReviewed(true)
                toast.success('Known account context confirmed')
              }}
            >
              {accountReviewed ? 'Account Confirmed' : 'Confirm Known Account'}
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
              disabled={!reviewGate.hasCriticalMapping || hasBlockingMappingErrors}
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
            rule={inboundAmountRule}
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
            rule={outboundAmountRule}
          />
          <FlowCard
            title="Deposit"
            tone="green"
            left={<FlowNode icon={<Wallet size={16} />} label="Cash / Money Source" accent="green" />}
            middle={<ArrowRight size={16} className="text-success" />}
            right={<FlowNode icon={<Building2 size={16} />} label="Subject Bank / Account" accent="blue" />}
            detail="If no real counterparty is present, an inbound money source is treated like deposit into the bank account."
            rule={hasDirectionMarkerAmount ? 'CR / IN marker with no counterparty -> Deposit' : hasSignedAmount ? 'Positive amount with no counterparty -> Deposit' : 'Credit without transfer identity -> Deposit'}
          />
          <FlowCard
            title="Withdraw"
            tone="red"
            left={<FlowNode icon={<Building2 size={16} />} label="Subject Bank / Account" accent="blue" />}
            middle={<ArrowRight size={16} className="text-danger" />}
            right={<FlowNode icon={<Wallet size={16} />} label="Cash / Money Out" accent="red" />}
            detail="If money leaves the bank without a real counterparty, BSIE maps it as withdrawal or cash-out."
            rule={hasDirectionMarkerAmount ? 'DR / OUT marker with no counterparty -> Withdraw' : hasSignedAmount ? 'Negative amount with no counterparty -> Withdraw' : 'Debit without transfer identity -> Withdraw'}
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

      <Card>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <CardTitle className="!mb-1">Mapping Validation</CardTitle>
            <p className="text-sm text-muted">
              Conflicts are blocked before BSIE stores this mapping or starts normalization.
            </p>
          </div>
          <Badge variant={hasBlockingMappingErrors ? 'red' : mappingValidation.warnings.length ? 'blue' : 'green'}>
            {hasBlockingMappingErrors ? 'Blocked' : mappingValidation.warnings.length ? 'Needs Review' : 'Ready'}
          </Badge>
        </div>

        <div className="space-y-2">
          {mappingValidation.errors.map(issue => (
            <div key={`${issue.code}:${issue.field || issue.column || issue.message}`} className="rounded-lg border border-danger/25 bg-danger/[0.06] px-3 py-2 text-xs text-text2">
              <span className="font-semibold text-danger">Blocker:</span> {issue.message}
            </div>
          ))}
          {mappingValidation.warnings.map(issue => (
            <div key={`${issue.code}:${issue.field || issue.column || issue.message}`} className="rounded-lg border border-warning/25 bg-warning/[0.08] px-3 py-2 text-xs text-text2">
              <span className="font-semibold text-warning">Review:</span> {issue.message}
            </div>
          ))}
          {!hasBlockingMappingErrors && mappingValidation.warnings.length === 0 && (
            <div className="rounded-lg border border-success/25 bg-success/[0.08] px-3 py-2 text-xs text-text2">
              Required fields are mapped and no duplicate column assignments were found.
            </div>
          )}
        </div>

        {serverPreview?.dry_run_preview && (
          <div className="mt-4 border-t border-border pt-4">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <Badge variant="blue">Dry-run preview</Badge>
              <span className="text-xs text-muted">
                {serverPreview.dry_run_preview.summary?.valid_transaction_rows || 0} of {serverPreview.dry_run_preview.summary?.preview_row_count || 0} sample rows parse as transactions.
              </span>
            </div>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-surface2 text-muted">
                    <th className="px-2 py-1.5 text-left">Row</th>
                    <th className="px-2 py-1.5 text-left">Date</th>
                    <th className="px-2 py-1.5 text-left">Amount</th>
                    <th className="px-2 py-1.5 text-left">Direction</th>
                    <th className="px-2 py-1.5 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {serverPreview.dry_run_preview.rows?.slice(0, 5).map((row: any) => (
                    <tr key={row.row_index} className="border-t border-border/60">
                      <td className="px-2 py-1.5 text-text2">{row.row_index}</td>
                      <td className="px-2 py-1.5 text-text2">{row.date || '-'}</td>
                      <td className="px-2 py-1.5 text-text2">{row.amount ?? '-'}</td>
                      <td className="px-2 py-1.5 text-text2">{row.direction}</td>
                      <td className="px-2 py-1.5">
                        <Badge variant={row.status === 'ok' ? 'green' : row.status === 'rejected' ? 'red' : 'blue'}>{row.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <CardTitle className="!mb-1">{t('step2.assist.title')}</CardTitle>
            <p className="text-sm text-muted">{t('step2.assist.description')}</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button size="sm" variant="outline" onClick={handleMappingAssist} disabled={assistLoading || allColumns.length === 0}>
              {assistLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              {assistLoading ? t('step2.assist.running') : t('step2.assist.run')}
            </Button>
            {isVisionAssistAvailable && (
              <Button size="sm" variant="outline" onClick={handleVisionMappingAssist} disabled={assistLoading || allColumns.length === 0}>
                {assistLoading ? <Loader2 size={13} className="animate-spin" /> : <FileSearch size={13} />}
                {assistLoading ? t('step2.assist.visionRunning') : t('step2.assist.runVision')}
              </Button>
            )}
          </div>
        </div>

        {!mappingAssist && (
          <div className="rounded-lg border border-border/70 bg-surface2/40 px-3 py-2 text-xs text-muted">
            {t('step2.assist.empty')}
          </div>
        )}

        {mappingAssist && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={mappingAssist.validation?.ok ? 'green' : 'yellow'}>
                {mappingAssist.validation?.ok ? t('step2.assist.valid') : t('step2.assist.needsReview')}
              </Badge>
              <Badge variant="gray">{mappingAssist.model || 'local-llm'}</Badge>
              <Badge variant="blue">{Math.round(Number(mappingAssist.confidence || 0) * 100)}%</Badge>
              <Badge variant="gray">{t('step2.assist.suggestionOnly')}</Badge>
              {mappingAssist.source === 'local_llm_vision_mapping_assist' && (
                <Badge variant="blue">{t('step2.assist.vision')}</Badge>
              )}
            </div>

            {Array.isArray(mappingAssist.reasons) && mappingAssist.reasons.length > 0 && (
              <div className="rounded-lg border border-border/70 bg-surface2/40 p-3">
                <div className="mb-2 text-[11px] uppercase text-muted font-semibold">{t('step2.assist.reasons')}</div>
                <div className="space-y-1">
                  {mappingAssist.reasons.map((reason: string) => (
                    <div key={reason} className="text-xs text-text2">{reason}</div>
                  ))}
                </div>
              </div>
            )}

            {[
              ...(Array.isArray(mappingAssist.warnings) ? mappingAssist.warnings : []),
              ...(Array.isArray(mappingAssist.validation?.errors) ? mappingAssist.validation.errors.map((item: any) => item.message) : []),
              ...(Array.isArray(mappingAssist.validation?.warnings) ? mappingAssist.validation.warnings.map((item: any) => item.message) : []),
            ].length > 0 && (
              <div className="rounded-lg border border-warning/25 bg-warning/[0.08] p-3">
                <div className="mb-2 text-[11px] uppercase text-muted font-semibold">{t('step2.assist.warnings')}</div>
                <div className="space-y-1">
                  {[
                    ...(Array.isArray(mappingAssist.warnings) ? mappingAssist.warnings : []),
                    ...(Array.isArray(mappingAssist.validation?.errors) ? mappingAssist.validation.errors.map((item: any) => item.message) : []),
                    ...(Array.isArray(mappingAssist.validation?.warnings) ? mappingAssist.validation.warnings.map((item: any) => item.message) : []),
                  ].map((warning: string) => (
                    <div key={warning} className="text-xs text-text2">{warning}</div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-1.5">
              {Object.entries(mappingAssist.mapping || {})
                .filter(([, column]) => !!column)
                .map(([field, column]) => (
                  <span key={field} className="rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-text2">
                    {field} → {String(column)}
                  </span>
                ))}
            </div>

            <Button size="sm" variant="primary" onClick={applyMappingAssist}>
              <Sparkles size={13} />{t('step2.assist.apply')}
            </Button>
          </div>
        )}
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
                const conflict = !!val && mappingValidation.duplicateColumns.includes(val)
                return (
                  <tr key={key} className="border-b border-border/50 hover:bg-surface2/50 transition-colors">
                    <td className="py-2.5 px-3 font-medium text-text2">
                      {label}{required && <span className="text-danger ml-1">{t('step2.required')}</span>}
                    </td>
                    <td className="py-2.5 px-3">
                      <select
                        value={val}
                        onChange={e => update(key, e.target.value)}
                        className="bg-surface2 border border-border rounded-lg px-2 py-1 text-sm text-text w-full max-w-[220px] focus:border-accent outline-none cursor-pointer"
                      >
                        <option value="">{t('step2.unmapped')}</option>
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
                      <Badge variant={conflict ? 'red' : mapped ? 'green' : 'gray'}>{conflict ? 'Conflict' : mapped ? 'Mapped' : 'Unmapped'}</Badge>
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
        <Button onClick={handleConfirm} disabled={saving || !canProceedToConfig || hasBlockingMappingErrors}>
          {saving ? t('step2.confirming') : <><ChevronRight size={14} />{t('step2.confirmMapping')}</>}
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
                    <option value="direction_marker">Direction marker (amount + DR/CR)</option>
                    <option value="dual_account">Dual Account (debit + credit)</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] uppercase text-muted font-semibold">Amount Mode</label>
                  <select value={learnForm.amount_mode}
                    onChange={e => setLearnForm(f => ({ ...f, amount_mode: e.target.value }))}
                    className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none cursor-pointer">
                    <option value="signed">Signed (single +/- column)</option>
                    <option value="direction_marker">Amount + Direction Marker</option>
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

function normalizeAccount(value: unknown) {
  const digits = String(value || '').replace(/\D/g, '')
  return digits.length === 10 || digits.length === 12 ? digits : ''
}

function evaluateLocalMapping(mapping: Record<string, string | null>, columns: string[]) {
  const errors: Array<{ code: string; message: string; field?: string; column?: string }> = []
  const warnings: Array<{ code: string; message: string; field?: string; column?: string }> = []
  const availableColumns = new Set(columns)
  const mappedColumns = new Map<string, string[]>()

  Object.entries(mapping || {}).forEach(([field, column]) => {
    if (!column) return
    if (!availableColumns.has(column)) {
      errors.push({
        code: 'unknown_column',
        field,
        column,
        message: `Mapped column "${column}" is not present in the uploaded sheet.`,
      })
      return
    }
    mappedColumns.set(column, [...(mappedColumns.get(column) || []), field])
  })

  const duplicateColumns: string[] = []
  mappedColumns.forEach((fields, column) => {
    if (fields.length > 1) {
      duplicateColumns.push(column)
      errors.push({
        code: 'duplicate_column_assignment',
        column,
        message: `Column "${column}" is assigned to multiple fields: ${fields.join(', ')}.`,
      })
    }
  })

  if (!mapping.date) {
    errors.push({ code: 'missing_required_field', field: 'date', message: 'Date field is required.' })
  }
  if (!mapping.description) {
    errors.push({ code: 'missing_required_field', field: 'description', message: 'Description field is required.' })
  }

  const hasAmount = !!mapping.amount
  const hasDirectionMarker = !!mapping.direction_marker
  const hasDebit = !!mapping.debit
  const hasCredit = !!mapping.credit
  if (!hasAmount && !hasDebit && !hasCredit) {
    errors.push({ code: 'missing_amount_path', message: 'Map either a signed amount column, an amount + direction marker pair, or at least one debit/credit column.' })
  }
  if (hasDirectionMarker && !hasAmount) {
    errors.push({ code: 'direction_marker_requires_amount', field: 'amount', message: 'Direction marker layouts must also map the unsigned amount column.' })
  }
  if ((hasAmount || hasDirectionMarker) && (hasDebit || hasCredit)) {
    errors.push({ code: 'conflicting_amount_paths', message: 'Use either signed/direction-marker amount or debit/credit columns, not both.' })
  }
  if (!hasDirectionMarker && ((hasDebit && !hasCredit) || (hasCredit && !hasDebit))) {
    warnings.push({
      code: 'one_sided_amount_path',
      field: hasDebit ? 'credit' : 'debit',
      message: `Only ${hasDebit ? 'debit' : 'credit'} is mapped; the opposite side may need review.`,
    })
  }

  return { errors, warnings, duplicateColumns }
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
