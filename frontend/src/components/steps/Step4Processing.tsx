import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getJobStatus } from '@/api'
import { useStore } from '@/store'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'

export function Step4Processing() {
  const { t } = useTranslation()
  const { jobId, setStep, setResults } = useStore()
  const logRef = useRef<HTMLDivElement>(null)
  const handledRef = useRef(false)

  const { data } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => getJobStatus(jobId!),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return (status === 'done' || status === 'error') ? false : 1200
    },
    enabled: !!jobId,
  })

  useEffect(() => {
    if (!data || handledRef.current) return
    if (data.status === 'done') {
      handledRef.current = true
      setResults(data.result)
      setStep(5)
      toast.success(t('step4.pipelineComplete'))
    } else if (data.status === 'error') {
      handledRef.current = true
      toast.error(`${t('step4.pipelineFailed')}${data.error || 'Unknown error'}`)
    }
  }, [data, data?.status, setResults, setStep, t])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [data?.log])

  const lines: string[] = data?.log || []
  const status: string  = data?.status || 'queued'

  return (
    <div className="max-w-2xl space-y-5">
      <div className="flex items-center gap-3">
        {status !== 'done' && status !== 'error' && (
          <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin shrink-0" />
        )}
        <div>
          <h2 className="text-lg font-bold text-text">{t('step4.title')}</h2>
          <p className="text-muted text-sm capitalize">
            {status === 'queued' ? t('step4.waiting') : status === 'running' ? t('step4.running') : status}
          </p>
        </div>
      </div>

      <div
        ref={logRef}
        className="bg-surface2 rounded-xl p-4 h-64 overflow-y-auto font-mono text-xs space-y-0.5 border border-border"
      >
        {lines.length === 0 ? (
          <p className="text-muted">{t('step4.waitingForPipeline')}</p>
        ) : (
          lines.map((line, i) => (
            <div
              key={i}
              className={
                line.includes('WARNING') ? 'text-warning' :
                line.includes('ERROR')   ? 'text-danger'  :
                'text-text2'
              }
            >
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
