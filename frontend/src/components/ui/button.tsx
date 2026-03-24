import { cn } from '@/lib/utils'
import { type ButtonHTMLAttributes, forwardRef } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'success' | 'danger' | 'ghost' | 'outline'
  size?: 'sm' | 'md'
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className, children, ...props }, ref) => {
    const base = 'inline-flex items-center gap-1.5 font-semibold rounded-lg transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed'
    const sizes = { sm: 'px-2.5 py-1 text-xs', md: 'px-4 py-2 text-sm' }
    const variants = {
      primary: 'bg-accent text-black hover:bg-accent2',
      success: 'bg-success text-black hover:opacity-90',
      danger:  'bg-danger text-white hover:opacity-90',
      ghost:   'bg-transparent text-muted border border-border hover:border-accent hover:text-accent',
      outline: 'bg-transparent border border-border text-text2 hover:border-accent hover:text-accent',
    }
    return (
      <button ref={ref} className={cn(base, sizes[size], variants[variant], className)} {...props}>
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'
