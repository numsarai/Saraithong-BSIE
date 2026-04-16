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
import { Upload, Search, Settings, Cpu, BarChart2, Building2, FolderTree, Database, Globe, LayoutDashboard, Menu, X, Moon, SunMedium } from 'lucide-react'
import { useState } from 'react'

export function Sidebar() {
  const { t } = useTranslation()
  const step = useStore(s => s.step)
  const page = useStore(s => s.page)
  const locale = useStore(s => s.locale)
  const theme = useStore(s => s.theme)
  const operatorName = useStore(s => s.operatorName)
  const setPage = useStore(s => s.setPage)
  const setOperatorName = useStore(s => s.setOperatorName)
  const setStep = useStore(s => s.setStep)
  const setLocale = useStore(s => s.setLocale)
  const setTheme = useStore(s => s.setTheme)

  const STEPS = [
    { n: 1, label: t('sidebar.steps.upload'),    icon: Upload },
    { n: 2, label: t('sidebar.steps.detectMap'), icon: Search },
    { n: 3, label: t('sidebar.steps.configure'), icon: Settings },
    { n: 4, label: t('sidebar.steps.processing'),icon: Cpu },
    { n: 5, label: t('sidebar.steps.results'),   icon: BarChart2 },
  ]

  const goHome = () => { setPage('main') }

  const goToStep = (n: number) => {
    if (n <= step) { setPage('main'); setStep(n) }
  }

  const [collapsed, setCollapsed] = useState(false)

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="fixed top-3 left-3 z-50 md:hidden p-2.5 rounded-lg bg-surface border border-border text-muted hover:text-text cursor-pointer shadow-sm"
      >
        {collapsed ? <X size={18} /> : <Menu size={18} />}
      </button>

    <aside className={cn(
      "shrink-0 bg-surface border-r border-border sticky top-0 h-screen py-5 px-3 flex flex-col transition-all z-40",
      "w-[220px]",
      "max-md:fixed max-md:top-0 max-md:left-0 max-md:shadow-lg",
      collapsed ? "max-md:translate-x-0" : "max-md:-translate-x-full",
    )}>
      {/* Logo + App Name */}
      <div className="px-2 mb-6 cursor-pointer" onClick={goHome}>
        <div className="flex items-center gap-2.5">
          <img
            src={APP_ICON_URL}
            alt={`${APP_NAME} app icon`}
            className="h-10 w-10 rounded-xl object-cover shadow-md ring-1 ring-border"
          />
          <div>
            <div className="text-sm font-bold text-text leading-tight">{APP_NAME}</div>
            <div className="text-[10px] text-muted leading-tight">{APP_SUBTITLE}</div>
          </div>
        </div>
        <span className="mt-2 inline-block text-[10px] bg-accent/12 text-accent px-2 py-0.5 rounded-full font-bold tracking-wide">
          v{APP_VERSION}
        </span>
      </div>

      {/* Steps */}
      <div className="space-y-0.5">
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
                'flex items-center gap-2.5 px-3 py-2.5 rounded-lg transition-all text-[13px] min-h-[40px]',
                isActive && 'bg-accent/10 text-accent font-semibold border border-accent/20',
                isDone   && 'text-success hover:bg-success/5',
                isLocked && 'opacity-35 text-muted',
                clickable && !isActive && 'cursor-pointer hover:bg-surface2',
                !clickable && 'cursor-not-allowed',
              )}
            >
              <div className={cn(
                'w-[22px] h-[22px] rounded-full border-2 flex items-center justify-center text-[11px] font-bold shrink-0',
                isActive && 'border-accent text-accent bg-accent/10',
                isDone   && 'border-success text-success bg-success/10',
                isLocked && 'border-border text-muted',
              )}>
                {isDone ? '\u2713' : n}
              </div>
              <span className="truncate">{label}</span>
              <Icon size={14} className="ml-auto opacity-50 shrink-0" />
            </div>
          )
        })}
      </div>

      {/* Bottom section */}
      <div className="mt-auto pt-4 border-t border-border space-y-1">
        {/* Language + Theme toggles */}
        <div className="flex items-center gap-2 px-2 mb-3">
          <div className="flex items-center gap-1.5">
            <Globe size={12} className="text-muted shrink-0" />
            <div className="flex rounded-md border border-border overflow-hidden text-[10px] font-semibold">
              <button
                onClick={() => setLocale('th')}
                className={cn(
                  'px-2.5 py-1 transition-colors cursor-pointer min-w-[28px]',
                  locale === 'th' ? 'bg-accent text-white' : 'bg-surface2 text-muted hover:text-text',
                )}
              >
                TH
              </button>
              <button
                onClick={() => setLocale('en')}
                className={cn(
                  'px-2.5 py-1 transition-colors cursor-pointer min-w-[28px]',
                  locale === 'en' ? 'bg-accent text-white' : 'bg-surface2 text-muted hover:text-text',
                )}
              >
                EN
              </button>
            </div>
          </div>
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="flex items-center gap-1.5 rounded-md border border-border bg-surface2 px-2.5 py-1 text-[10px] font-semibold text-muted hover:text-text hover:border-accent/40 transition-colors cursor-pointer"
            title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
          >
            {theme === 'dark' ? <SunMedium size={12} /> : <Moon size={12} />}
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
        </div>

        {/* Nav buttons */}
        {[
          { key: 'dashboard', icon: LayoutDashboard, label: t('sidebar.nav.dashboard') },
          { key: 'investigation', icon: Database, label: t('sidebar.nav.investigation') },
          { key: 'bulk-intake', icon: FolderTree, label: t('sidebar.nav.bulkIntake') },
          { key: 'bank-manager', icon: Building2, label: t('sidebar.nav.bankManager') },
        ].map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            onClick={() => setPage(key as any)}
            className={cn(
              'w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg transition-all text-[13px] min-h-[40px]',
              page === key
                ? 'bg-accent/10 text-accent font-semibold border border-accent/20'
                : 'text-muted hover:text-text hover:bg-surface2 cursor-pointer',
            )}
          >
            <Icon size={15} className="shrink-0" />
            <span className="truncate">{label}</span>
          </button>
        ))}

        {/* Operator input */}
        <label className="block px-2 pt-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">{t('sidebar.operatorLabel')}</div>
          <input
            value={operatorName}
            onChange={(event) => setOperatorName(event.target.value)}
            placeholder={t('sidebar.operatorPlaceholder')}
            maxLength={80}
            className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none transition-colors focus:border-accent focus:ring-1 focus:ring-accent/30"
          />
          <div className="mt-1 text-[10px] text-muted">{t('sidebar.operatorHint')}</div>
        </label>

        {/* Developer info */}
        <div className="mt-3 rounded-xl border border-border bg-surface2 px-3 py-3">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">{t('sidebar.developerLabel')}</div>
          <div className="mt-1 text-[11px] font-medium leading-snug text-text">{APP_DEVELOPER_NAME}</div>
          <div className="mt-1 text-[10px] text-muted">{t('sidebar.contact')} {APP_CONTACT_PHONE}</div>
        </div>
      </div>
    </aside>
    </>
  )
}
