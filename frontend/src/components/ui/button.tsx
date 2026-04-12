import { cn } from '@/lib/utils'
import { type ButtonHTMLAttributes, forwardRef } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'success' | 'danger' | 'ghost' | 'outline'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className, children, ...props }, ref) => {
    const base = [
      'inline-flex items-center justify-center gap-1.5 font-semibold rounded-lg',
      'transition-all duration-200 ease-out',
      'cursor-pointer select-none',
      'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent',
      'disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none',
      'active:scale-[0.97]',
    ].join(' ')

    const sizes: Record<string, string> = {
      sm:  'min-h-[32px] px-2.5 py-1 text-xs',
      md:  'min-h-[40px] px-4 py-2 text-sm',
      lg:  'min-h-[44px] px-5 py-2.5 text-base',
    }

    const variants: Record<string, string> = {
      primary: 'bg-accent text-white hover:bg-accent2 shadow-sm hover:shadow',
      success: 'bg-success text-white hover:brightness-110 shadow-sm hover:shadow',
      danger:  'bg-danger text-white hover:brightness-110 shadow-sm hover:shadow',
      ghost:   'bg-transparent text-muted hover:bg-surface2 hover:text-text',
      outline: 'bg-transparent border border-border text-text2 hover:border-accent hover:text-accent hover:bg-accent/5',
    }

    return (
      <button
        ref={ref}
        className={cn(base, sizes[size], variants[variant], className)}
        {...props}
      >
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'
