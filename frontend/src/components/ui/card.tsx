import { cn } from '@/lib/utils'

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn(
      'bg-surface border border-border rounded-xl p-5',
      'shadow-card transition-theme',
      className
    )}>
      {children}
    </div>
  )
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <h3 className={cn('text-base font-semibold flex items-center gap-2 mb-3 text-text', className)}>
      {children}
    </h3>
  )
}
