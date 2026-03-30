import { cn } from '@/lib/utils'

export function Badge({ children, variant = 'blue' }: {
  children: React.ReactNode
  variant?: 'blue' | 'green' | 'red' | 'gray' | 'yellow'
}) {
  const v = {
    blue:  'bg-accent/15 text-accent',
    green: 'bg-success/15 text-success',
    red:   'bg-danger/15 text-danger',
    gray:  'bg-surface3 text-muted',
    yellow: 'bg-warning/15 text-warning',
  }
  return (
    <span className={cn('inline-block px-2 py-0.5 rounded-full text-xs font-bold', v[variant])}>
      {children}
    </span>
  )
}
