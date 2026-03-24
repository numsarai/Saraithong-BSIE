import { Toaster } from 'sonner'
import { Sidebar } from '@/components/Sidebar'
import { Step1Upload }     from '@/components/steps/Step1Upload'
import { Step2Map }        from '@/components/steps/Step2Map'
import { Step3Config }     from '@/components/steps/Step3Config'
import { Step4Processing } from '@/components/steps/Step4Processing'
import { Step5Results }    from '@/components/steps/Step5Results'
import { BankManager }     from '@/components/BankManager'
import { useStore } from '@/store'

const STEPS = [Step1Upload, Step2Map, Step3Config, Step4Processing, Step5Results]

export default function App() {
  const step = useStore(s => s.step)
  const isBankManager = window.location.pathname === '/bank-manager'
  const StepComponent = STEPS[step - 1]

  return (
    <div className="flex min-h-screen bg-bg text-text">
      <Sidebar />
      <main className="flex-1 p-7 overflow-auto">
        {isBankManager ? <BankManager /> : <StepComponent />}
      </main>
      <Toaster theme="dark" position="bottom-right" richColors />
    </div>
  )
}
