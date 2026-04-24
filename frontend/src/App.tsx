import { lazy, Suspense, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Toaster } from 'sonner'
import { Sidebar } from '@/components/Sidebar'
import { useStore } from '@/store'
import { clearStoredAuthToken, getAuthStatus, getCurrentUser, getStoredAuthToken, login } from '@/api'

const Step1Upload = lazy(() => import('@/components/steps/Step1Upload').then(m => ({ default: m.Step1Upload })))
const Step2Map = lazy(() => import('@/components/steps/Step2Map').then(m => ({ default: m.Step2Map })))
const Step3Config = lazy(() => import('@/components/steps/Step3Config').then(m => ({ default: m.Step3Config })))
const Step4Processing = lazy(() => import('@/components/steps/Step4Processing').then(m => ({ default: m.Step4Processing })))
const Step5Results = lazy(() => import('@/components/steps/Step5Results').then(m => ({ default: m.Step5Results })))

// Lazy-load heavy pages to reduce initial bundle
const BankManager = lazy(() => import('@/components/BankManager').then(m => ({ default: m.BankManager })))
const BulkIntake = lazy(() => import('@/components/BulkIntake').then(m => ({ default: m.BulkIntake })))
const InvestigationDesk = lazy(() => import('@/components/InvestigationDesk').then(m => ({ default: m.InvestigationDesk })))
const Dashboard = lazy(() => import('@/components/Dashboard').then(m => ({ default: m.Dashboard })))

const STEPS = [Step1Upload, Step2Map, Step3Config, Step4Processing, Step5Results]

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

type AuthUser = {
  username: string
  role: string
}

function LoginScreen({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const { t } = useTranslation()
  const theme = useStore(s => s.theme)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const payload = await login(username, password)
      onAuthenticated(payload.user)
    } catch {
      setError(t('auth.invalidCredentials'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg text-text flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-lg border border-border bg-surface p-5 shadow-sm space-y-4">
        <div>
          <h1 className="text-lg font-semibold text-text">{t('auth.title')}</h1>
          <p className="mt-1 text-sm text-text2">{t('auth.subtitle')}</p>
        </div>
        <label className="block space-y-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">{t('auth.username')}</span>
          <input
            autoFocus
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">{t('auth.password')}</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent"
          />
        </label>
        {error && <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</div>}
        <button
          type="submit"
          disabled={!username.trim() || !password || submitting}
          className="w-full rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? t('auth.signingIn') : t('auth.signIn')}
        </button>
      </form>
      <Toaster theme={theme} position="bottom-right" richColors />
    </div>
  )
}

export default function App() {
  const { t } = useTranslation()
  const step = useStore(s => s.step)
  const page = useStore(s => s.page)
  const theme = useStore(s => s.theme)
  const [authReady, setAuthReady] = useState(false)
  const [authRequired, setAuthRequired] = useState(false)
  const [authUser, setAuthUser] = useState<AuthUser | null>(null)
  const StepComponent = STEPS[step - 1]

  // Apply dark class on mount and when theme changes
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  useEffect(() => {
    let active = true
    async function loadAuthState() {
      try {
        const status = await getAuthStatus()
        if (!active) return
        const required = Boolean(status.auth_required)
        setAuthRequired(required)
        if (!required) {
          setAuthReady(true)
          return
        }
        if (!getStoredAuthToken()) {
          setAuthReady(true)
          return
        }
        try {
          const payload = await getCurrentUser()
          if (active) setAuthUser(payload.user)
        } catch {
          clearStoredAuthToken()
        } finally {
          if (active) setAuthReady(true)
        }
      } catch {
        if (active) setAuthReady(true)
      }
    }
    loadAuthState()
    return () => {
      active = false
    }
  }, [])

  if (!authReady) {
    return (
      <div className="min-h-screen bg-bg text-text">
        <LoadingFallback />
        <Toaster theme={theme} position="bottom-right" richColors />
      </div>
    )
  }

  if (authRequired && !authUser) {
    return <LoginScreen onAuthenticated={(user) => setAuthUser(user)} />
  }

  const handleLogout = () => {
    clearStoredAuthToken()
    setAuthUser(null)
  }

  return (
    <div className="flex min-h-screen bg-bg text-text">
      <Sidebar />
      <main className="flex-1 p-7 overflow-auto">
        {authRequired && authUser && (
          <div className="mb-4 flex items-center justify-end gap-3 text-xs text-text2">
            <span>{t('auth.signedInAs', { username: authUser.username, role: authUser.role })}</span>
            <button
              onClick={handleLogout}
              className="rounded-md border border-border bg-surface px-2.5 py-1 font-semibold text-muted hover:border-accent/40 hover:text-text"
            >
              {t('auth.logout')}
            </button>
          </div>
        )}
        <Suspense fallback={<LoadingFallback />}>
          {page === 'dashboard'
            ? <Dashboard />
            : page === 'bank-manager'
              ? <BankManager />
              : page === 'bulk-intake'
                ? <BulkIntake />
                : page === 'investigation'
                  ? <InvestigationDesk />
                  : <StepComponent />}
        </Suspense>
      </main>
      <Toaster theme={theme} position="bottom-right" richColors />
    </div>
  )
}
