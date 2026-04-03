import { cn } from '@/lib/utils'
import { Building2 } from 'lucide-react'

type BankLogoLike = {
  key?: string
  name?: string
  logo_url?: string
}

const SIZE_CLASS = {
  sm: 'h-8 w-8 rounded-lg',
  md: 'h-10 w-10 rounded-xl',
  lg: 'h-12 w-12 rounded-2xl',
} as const

export function BankLogo({
  bank,
  size = 'md',
  className,
}: {
  bank?: BankLogoLike | null
  size?: keyof typeof SIZE_CLASS
  className?: string
}) {
  const src = bank?.logo_url || (bank?.key ? `/api/bank-logos/${bank.key}.svg` : '')
  const alt = `${bank?.name || bank?.key || 'Bank'} logo`
  const shapeClass = SIZE_CLASS[size] || SIZE_CLASS.md

  if (!src) {
    return (
      <div className={cn('flex items-center justify-center border border-border bg-surface2 text-muted', shapeClass, className)}>
        <Building2 size={16} />
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      className={cn('border border-border/70 bg-white object-contain p-1 shadow-sm', shapeClass, className)}
      loading="lazy"
    />
  )
}
