import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { FileSpreadsheet } from 'lucide-react'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { uploadFile } from '@/api'
import { normalizeOperatorName, useStore } from '@/store'

export function Step1Upload() {
  const { t } = useTranslation()
  const [uploading, setUploading] = useState(false)
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

      // If file was already processed, skip directly to Step 5 (Results)
      if (data.already_processed && data.prior_result) {
        const prior = data.prior_result
        setBankKey(prior.bank_key || '')
        setAccount(prior.account || '')
        setName(prior.subject_name || '')
        setParserRunId(prior.parser_run_id || null)
        setResults({ account: prior.account, meta: prior })
        setStep(5)
        toast.success(t('step1.alreadyProcessed'))
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
  }, [operatorName, setUploadResult, setStep, setBankKey, setAccount, setName, setParserRunId, setResults, t])

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
    </div>
  )
}
