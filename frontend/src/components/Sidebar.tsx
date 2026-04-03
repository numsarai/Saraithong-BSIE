import { useStore } from '@/store'
import { cn } from '@/lib/utils'
import { APP_ICON_URL, APP_NAME, APP_SUBTITLE, APP_VERSION } from '@/config/appMeta'
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
  const operatorName = useStore(s => s.operatorName)
  const setPage = useStore(s => s.setPage)
  const setOperatorName = useStore(s => s.setOperatorName)
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
          <img
            src={APP_ICON_URL}
            alt={`${APP_NAME} app icon`}
            className="h-11 w-11 rounded-[12px] object-cover shadow-[0_10px_24px_rgba(2,8,23,0.28)] ring-1 ring-white/8"
          />
          <div>
            <div className="text-sm font-bold text-text leading-tight">{APP_NAME}</div>
            <div className="text-[10px] text-muted leading-tight">{APP_SUBTITLE}</div>
          </div>
        </div>
        <span className="mt-2 inline-block text-[10px] bg-accent/15 text-accent px-2 py-0.5 rounded-full font-bold">
          v{APP_VERSION}
        </span>
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
        <label className="mb-3 block px-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted">Operator / Reviewer</div>
          <input
            value={operatorName}
            onChange={(event) => setOperatorName(event.target.value)}
            placeholder="Case Analyst"
            maxLength={80}
            className="w-full rounded-lg border border-border bg-surface2 px-2.5 py-2 text-sm text-text outline-none transition-colors focus:border-accent"
          />
          <div className="mt-1 text-[10px] text-muted">Used for upload, review, export, and admin audit logs.</div>
        </label>
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
