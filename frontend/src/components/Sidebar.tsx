import { useStore } from '@/store'
import { cn } from '@/lib/utils'
import { Upload, Search, Settings, Cpu, BarChart2, Building2, FolderTree, Database } from 'lucide-react'

const STEPS = [
  { n: 1, label: 'Upload File',   icon: Upload },
  { n: 2, label: 'Detect & Map', icon: Search },
  { n: 3, label: 'Configure',    icon: Settings },
  { n: 4, label: 'Processing',   icon: Cpu },
  { n: 5, label: 'Results',      icon: BarChart2 },
]

export function Sidebar() {
  const step = useStore(s => s.step)
  const page = useStore(s => s.page)
  const setPage = useStore(s => s.setPage)
  const setStep = useStore(s => s.setStep)

  const goHome = () => {
    setPage('main')
  }

  const goToStep = (n: number) => {
    // Allow clicking on completed steps or the current step
    if (n <= step) {
      setPage('main')
      setStep(n)
    }
  }

  return (
    <aside className="w-[210px] shrink-0 bg-surface border-r border-border sticky top-0 h-screen py-6 px-3 flex flex-col gap-1">
      <div className="px-2 mb-5 cursor-pointer" onClick={goHome}>
        <div className="flex items-center gap-2">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#58a6ff" strokeWidth="2">
            <rect x="2" y="7" width="20" height="14" rx="2"/>
            <path d="M16 7V5a2 2 0 0 0-4 0v2"/>
            <line x1="12" y1="12" x2="12" y2="16"/>
            <line x1="10" y1="14" x2="14" y2="14"/>
          </svg>
          <div>
            <div className="text-sm font-bold text-text leading-tight">BSIE</div>
            <div className="text-[10px] text-muted leading-tight">Intelligence Engine</div>
          </div>
        </div>
        <span className="mt-2 inline-block text-[10px] bg-accent/15 text-accent px-2 py-0.5 rounded-full font-bold">v2.0</span>
      </div>

      {STEPS.map(({ n, label, icon: Icon }) => {
        const isActive = page === 'main' && step === n
        const isDone   = step > n
        const isLocked = step < n
        const clickable = n <= step
        return (
          <div
            key={n}
            onClick={() => goToStep(n)}
            className={cn(
              'flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-[13px]',
              isActive && 'bg-accent/[0.13] text-accent font-semibold',
              isDone   && 'text-success',
              isLocked && 'opacity-35 text-muted',
              clickable && 'cursor-pointer hover:bg-accent/[0.08]',
              !clickable && 'cursor-not-allowed',
            )}
          >
            <div className={cn(
              'w-[21px] h-[21px] rounded-full border-2 flex items-center justify-center text-[11px] font-bold shrink-0',
              isActive && 'border-accent text-accent',
              isDone   && 'border-success text-success bg-success/10',
              isLocked && 'border-border text-muted',
            )}>
              {isDone ? '✓' : n}
            </div>
            <span>{label}</span>
            <Icon size={14} className="ml-auto opacity-60" />
          </div>
        )
      })}

      {/* Divider + Bank Manager link */}
      <div className="mt-auto pt-4 border-t border-border">
        <button
          onClick={() => setPage('investigation')}
          className={cn(
            'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-[13px] text-muted hover:text-accent hover:bg-accent/[0.08] cursor-pointer',
            page === 'investigation' && 'bg-accent/[0.13] text-accent font-semibold',
          )}
        >
          <Database size={14} className="shrink-0" />
          <span>Investigation</span>
        </button>
        <button
          onClick={() => setPage('bulk-intake')}
          className={cn(
            'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-[13px] text-muted hover:text-accent hover:bg-accent/[0.08] cursor-pointer',
            page === 'bulk-intake' && 'bg-accent/[0.13] text-accent font-semibold',
          )}
        >
          <FolderTree size={14} className="shrink-0" />
          <span>Bulk Intake</span>
        </button>
        <button
          onClick={() => setPage('bank-manager')}
          className={cn(
            'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-[13px] text-muted hover:text-accent hover:bg-accent/[0.08] cursor-pointer',
            page === 'bank-manager' && 'bg-accent/[0.13] text-accent font-semibold',
          )}
        >
          <Building2 size={14} className="shrink-0" />
          <span>Bank Manager</span>
        </button>
      </div>
    </aside>
  )
}
