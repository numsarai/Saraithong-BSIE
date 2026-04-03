import { Toaster } from 'sonner'
import { Sidebar } from '@/components/Sidebar'
import { Step1Upload }     from '@/components/steps/Step1Upload'
import { Step2Map }        from '@/components/steps/Step2Map'
import { Step3Config }     from '@/components/steps/Step3Config'
import { Step4Processing } from '@/components/steps/Step4Processing'
import { Step5Results }    from '@/components/steps/Step5Results'
import { BankManager }     from '@/components/BankManager'
import { BulkIntake }      from '@/components/BulkIntake'
import { InvestigationDesk } from '@/components/InvestigationDesk'
import { useStore } from '@/store'

const STEPS = [Step1Upload, Step2Map, Step3Config, Step4Processing, Step5Results]

export default function App() {
  const step = useStore(s => s.step)
  const page = useStore(s => s.page)
  const StepComponent = STEPS[step - 1]

  return (
    <div className="flex min-h-screen bg-bg text-text">
      <Sidebar />
      <main className="flex-1 p-7 overflow-auto">
        {page === 'bank-manager'
          ? <BankManager />
          : page === 'bulk-intake'
            ? <BulkIntake />
            : page === 'investigation'
              ? <InvestigationDesk />
              : <StepComponent />}
      </main>
      <Toaster theme="dark" position="bottom-right" richColors />
    </div>
  )
}
