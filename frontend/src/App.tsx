import { lazy, Suspense, useEffect } from 'react'
import { Toaster } from 'sonner'
import { Sidebar } from '@/components/Sidebar'
import { Step1Upload }     from '@/components/steps/Step1Upload'
import { Step2Map }        from '@/components/steps/Step2Map'
import { Step3Config }     from '@/components/steps/Step3Config'
import { Step4Processing } from '@/components/steps/Step4Processing'
import { Step5Results }    from '@/components/steps/Step5Results'
import { useStore } from '@/store'

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

export default function App() {
  const step = useStore(s => s.step)
  const page = useStore(s => s.page)
  const theme = useStore(s => s.theme)
  const StepComponent = STEPS[step - 1]

  // Apply dark class on mount and when theme changes
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return (
    <div className="flex min-h-screen bg-bg text-text">
      <Sidebar />
      <main className="flex-1 p-7 overflow-auto">
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
