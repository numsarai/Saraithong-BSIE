import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { FileSpreadsheet, RotateCcw, FastForward } from 'lucide-react'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { uploadFile } from '@/api'
import { normalizeOperatorName, useStore } from '@/store'
import { Button } from '@/components/ui/button'
import { LlmChat } from '@/components/LlmChat'

interface PriorResult {
  parser_run_id: string
  account: string
  bank_key: string
  bank_name: string
  subject_name: string
  transaction_count: number
}

export function Step1Upload() {
  const { t } = useTranslation()
  const [uploading, setUploading] = useState(false)
  const [priorChoice, setPriorChoice] = useState<{ data: any; prior: PriorResult; fileName: string } | null>(null)
  const setUploadResult = useStore(s => s.setUploadResult)
  const setStep = useStore(s => s.setStep)
  const setResults = useStore(s => s.setResults)
  const setBankKey = useStore(s => s.setBankKey)
  const setAccount = useStore(s => s.setAccount)
  const setName = useStore(s => s.setName)
  const setParserRunId = useStore(s => s.setParserRunId)
  const operatorName = useStore(s => s.operatorName)

  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0]
    if (!file) return
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['xlsx', 'xls', 'ofx', 'pdf', 'png', 'jpg', 'jpeg', 'bmp'].includes(ext || '')) {
      toast.error(t('step1.fileTypeError'))
      return
    }
    setUploading(true)
    try {
      const data = await uploadFile(file, normalizeOperatorName(operatorName))

      // If file was already processed, let user choose
      if (data.already_processed && data.prior_result) {
        setPriorChoice({ data, prior: data.prior_result, fileName: file.name })
        setUploading(false)
        return
      }

      setUploadResult(data, file.name)
      setStep(2)
      toast.success(t('step1.uploadSuccess'))
    } catch (e: any) {
      toast.error(`Upload failed: ${e.message}`)
    } finally {
      setUploading(false)
    }
  }, [operatorName, setUploadResult, setStep, t])

  const handleViewPrior = () => {
    if (!priorChoice) return
    const prior = priorChoice.prior
    setBankKey(prior.bank_key || '')
    setAccount(prior.account || '')
    setName(prior.subject_name || '')
    setParserRunId(prior.parser_run_id || null)
    setResults({ account: prior.account, meta: prior })
    setStep(5)
    setPriorChoice(null)
    toast.success(t('step1.alreadyProcessed'))
  }

  const handleReprocess = useCallback(async () => {
    if (!priorChoice) return
    // Re-detect: call /api/redetect with the stored file path
    setUploading(true)
    setPriorChoice(null)
    try {
      const resp = await fetch('/api/redetect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_id: priorChoice.data.file_id,
          file_name: priorChoice.fileName,
        }),
      })
      if (!resp.ok) throw new Error(await resp.text())
      const data = await resp.json()
      setUploadResult(data, priorChoice.fileName)
      setStep(2)
      toast.success(t('step1.reprocessing'))
    } catch (e: any) {
      toast.error(`Reprocess failed: ${e.message}`)
    } finally {
      setUploading(false)
    }
  }, [priorChoice, setUploadResult, setStep, t])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/x-ofx': ['.ofx'],
      'application/ofx': ['.ofx'],
      'text/plain': ['.ofx'],
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/bmp': ['.bmp'],
    },
    multiple: false,
    disabled: uploading,
  })

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
    <div className="max-w-xl">
      <h2 className="text-lg font-bold mb-1 text-text">{t('step1.title')}</h2>
      <p className="text-muted text-sm mb-6">{t('step1.description')}</p>

      <div
        {...getRootProps()}
        className={[
          'border-2 border-dashed rounded-xl p-14 text-center cursor-pointer transition-all',
          isDragActive ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/50',
          uploading ? 'opacity-50 cursor-not-allowed' : '',
        ].join(' ')}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <p className="text-muted text-sm">{t('step1.analysing')}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <FileSpreadsheet size={44} className="text-muted" />
            <p className="text-text2 font-medium">{t('step1.dropHere')}</p>
            <p className="text-muted text-sm">
              {t('step1.or')} <span className="text-accent underline cursor-pointer">{t('step1.browse')}</span> {t('step1.toSelect')}
            </p>
            <p className="text-muted text-xs mt-1">{t('step1.fileTypes')}</p>
          </div>
        )}
      </div>

      {/* Prior result choice dialog */}
      {priorChoice && (
        <div className="mt-6 rounded-xl border border-accent/30 bg-accent/[0.06] p-5 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-text">{t('step1.duplicateFound')}</h3>
            <p className="text-xs text-muted mt-1">{t('step1.duplicateDescription')}</p>
          </div>
          <div className="rounded-lg bg-surface2 p-3 text-xs space-y-1">
            <div className="flex gap-2"><span className="text-muted w-16">{t('step3.account')}:</span><span className="text-text font-mono">{priorChoice.prior.account}</span></div>
            <div className="flex gap-2"><span className="text-muted w-16">{t('step3.name')}:</span><span className="text-text">{priorChoice.prior.subject_name}</span></div>
            <div className="flex gap-2"><span className="text-muted w-16">{t('step3.bank')}:</span><span className="text-text">{priorChoice.prior.bank_name}</span></div>
            <div className="flex gap-2"><span className="text-muted w-16">{t('results.stats.totalTxn')}:</span><span className="text-text">{priorChoice.prior.transaction_count?.toLocaleString()}</span></div>
          </div>
          <div className="flex gap-3">
            <Button variant="success" onClick={handleViewPrior}>
              <FastForward size={14} />
              {t('step1.viewPriorResults')}
            </Button>
            <Button variant="ghost" onClick={handleReprocess}>
              <RotateCcw size={14} />
              {t('step1.reprocessFile')}
            </Button>
          </div>
        </div>
      )}
    </div>

    {/* LLM Chat — right column */}
    <div className="lg:sticky lg:top-7">
      <LlmChat compact />
    </div>
    </div>
  )
}
