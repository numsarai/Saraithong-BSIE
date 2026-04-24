import { useState } from 'react'
import { Bot, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { LlmChat } from '@/components/LlmChat'
import { Button } from '@/components/ui/button'
import { CopilotTab } from '@/components/investigation/CopilotTab'

interface AiCopilotTabProps {
  operatorName: string
  selectedRunId?: string
  selectedFileId?: string
  selectedAccountNumber?: string
  filterRunId?: string
  filterFileId?: string
  crossAccountNumber?: string
}

export function AiCopilotTab(props: AiCopilotTabProps) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<'project' | 'evidence'>('project')

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-base font-semibold text-text">{t('investigation.aiCopilot.title')}</div>
        </div>
        <div className="inline-flex rounded-lg border border-border bg-surface2 p-1">
          <Button
            size="sm"
            variant={mode === 'project' ? 'primary' : 'ghost'}
            onClick={() => setMode('project')}
            className="min-w-28"
          >
            <Bot size={14} />
            {t('investigation.aiCopilot.projectMode')}
          </Button>
          <Button
            size="sm"
            variant={mode === 'evidence' ? 'primary' : 'ghost'}
            onClick={() => setMode('evidence')}
            className="min-w-28"
          >
            <ShieldCheck size={14} />
            {t('investigation.aiCopilot.evidenceMode')}
          </Button>
        </div>
      </div>

      {mode === 'project' ? (
        <LlmChat />
      ) : (
        <CopilotTab {...props} />
      )}
    </div>
  )
}
