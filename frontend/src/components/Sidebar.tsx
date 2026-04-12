import { useTranslation } from 'react-i18next'
import { useStore } from '@/store'
import { cn } from '@/lib/utils'
import {
  APP_CONTACT_PHONE,
  APP_DEVELOPER_NAME,
  APP_ICON_URL,
  APP_NAME,
  APP_SUBTITLE,
  APP_VERSION,
} from '@/config/appMeta'
import { Upload, Search, Settings, Cpu, BarChart2, Building2, FolderTree, Database, Globe, LayoutDashboard, Menu, X } from 'lucide-react'
import { useState } from 'react'

export function Sidebar() {
  const { t } = useTranslation()
  const step = useStore(s => s.step)
  const page = useStore(s => s.page)
  const locale = useStore(s => s.locale)
  const operatorName = useStore(s => s.operatorName)
  const setPage = useStore(s => s.setPage)
  const setOperatorName = useStore(s => s.setOperatorName)
  const setStep = useStore(s => s.setStep)
  const setLocale = useStore(s => s.setLocale)

  const STEPS = [
    { n: 1, label: t('sidebar.steps.upload'),    icon: Upload },
    { n: 2, label: t('sidebar.steps.detectMap'), icon: Search },
    { n: 3, label: t('sidebar.steps.configure'), icon: Settings },
    { n: 4, label: t('sidebar.steps.processing'),icon: Cpu },
    { n: 5, label: t('sidebar.steps.results'),   icon: BarChart2 },
  ]

  const goHome = () => {
    setPage('main')
  }

  const goToStep = (n: number) => {
    if (n <= step) {
      setPage('main')
      setStep(n)
    }
  }

  const [collapsed, setCollapsed] = useState(false)

  return (
    <>
      {/* Mobile toggle button */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="fixed top-3 left-3 z-50 md:hidden p-2 rounded-lg bg-surface border border-border text-muted hover:text-text cursor-pointer"
      >
        {collapsed ? <X size={18} /> : <Menu size={18} />}
      </button>

    <aside className={cn(
      "shrink-0 bg-surface border-r border-border sticky top-0 h-screen py-6 px-3 flex flex-col gap-1 transition-all z-40",
      "w-[210px]",
      // Mobile: hidden by default, show when collapsed=true (toggle is inverted naming)
      "max-md:fixed max-md:top-0 max-md:left-0 max-md:shadow-2xl",
      collapsed ? "max-md:translate-x-0" : "max-md:-translate-x-full",
    )}>
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
              {isDone ? '\u2713' : n}
            </div>
            <span>{label}</span>
            <Icon size={14} className="ml-auto opacity-60" />
          </div>
        )
      })}

      {/* Divider + controls */}
      <div className="mt-auto pt-4 border-t border-border">
        {/* Language toggle */}
        <div className="flex items-center gap-1.5 px-2 mb-3">
          <Globe size={12} className="text-muted shrink-0" />
          <div className="flex rounded-md border border-border overflow-hidden text-[10px] font-semibold">
            <button
              onClick={() => setLocale('th')}
              className={cn(
                'px-2 py-0.5 transition-colors cursor-pointer',
                locale === 'th' ? 'bg-accent text-white' : 'bg-surface2 text-muted hover:text-text',
              )}
            >
              TH
            </button>
            <button
              onClick={() => setLocale('en')}
              className={cn(
                'px-2 py-0.5 transition-colors cursor-pointer',
                locale === 'en' ? 'bg-accent text-white' : 'bg-surface2 text-muted hover:text-text',
              )}
            >
              EN
            </button>
          </div>
        </div>

        <button
          onClick={() => setPage('dashboard')}
          className={cn(
            'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-[13px] text-muted hover:text-accent hover:bg-accent/[0.08] cursor-pointer',
            page === 'dashboard' && 'bg-accent/[0.13] text-accent font-semibold',
          )}
        >
          <LayoutDashboard size={14} className="shrink-0" />
          <span>{t('sidebar.nav.dashboard')}</span>
        </button>
        <label className="mb-3 block px-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted">{t('sidebar.operatorLabel')}</div>
          <input
            value={operatorName}
            onChange={(event) => setOperatorName(event.target.value)}
            placeholder={t('sidebar.operatorPlaceholder')}
            maxLength={80}
            className="w-full rounded-lg border border-border bg-surface2 px-2.5 py-2 text-sm text-text outline-none transition-colors focus:border-accent"
          />
          <div className="mt-1 text-[10px] text-muted">{t('sidebar.operatorHint')}</div>
        </label>
        <button
          onClick={() => setPage('investigation')}
          className={cn(
            'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-[13px] text-muted hover:text-accent hover:bg-accent/[0.08] cursor-pointer',
            page === 'investigation' && 'bg-accent/[0.13] text-accent font-semibold',
          )}
        >
          <Database size={14} className="shrink-0" />
          <span>{t('sidebar.nav.investigation')}</span>
        </button>
        <button
          onClick={() => setPage('bulk-intake')}
          className={cn(
            'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-[13px] text-muted hover:text-accent hover:bg-accent/[0.08] cursor-pointer',
            page === 'bulk-intake' && 'bg-accent/[0.13] text-accent font-semibold',
          )}
        >
          <FolderTree size={14} className="shrink-0" />
          <span>{t('sidebar.nav.bulkIntake')}</span>
        </button>
        <button
          onClick={() => setPage('bank-manager')}
          className={cn(
            'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all text-[13px] text-muted hover:text-accent hover:bg-accent/[0.08] cursor-pointer',
            page === 'bank-manager' && 'bg-accent/[0.13] text-accent font-semibold',
          )}
        >
          <Building2 size={14} className="shrink-0" />
          <span>{t('sidebar.nav.bankManager')}</span>
        </button>
        <div className="mt-3 rounded-xl border border-border bg-surface2 px-3 py-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted">{t('sidebar.developerLabel')}</div>
          <div className="mt-1 text-[11px] font-medium leading-snug text-text">{APP_DEVELOPER_NAME}</div>
          <div className="mt-1 text-[10px] text-muted">{t('sidebar.contact')} {APP_CONTACT_PHONE}</div>
        </div>
      </div>
    </aside>
    </>

  )
}
