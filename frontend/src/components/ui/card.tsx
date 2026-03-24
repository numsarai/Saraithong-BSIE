import { cn } from '@/lib/utils'

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('bg-surface border border-border rounded-xl p-5 shadow-[0_2px_16px_rgba(0,0,0,.4)]', className)}>
      {children}
    </div>
  )
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('text-sm font-semibold flex items-center gap-2 mb-3', className)}>
      {children}
    </div>
  )
}
