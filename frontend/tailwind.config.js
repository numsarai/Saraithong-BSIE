/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       'var(--color-bg)',
        surface:  'var(--color-surface)',
        surface2: 'var(--color-surface2)',
        surface3: 'var(--color-surface3)',
        border:   'var(--color-border)',
        accent:   'var(--color-accent)',
        accent2:  'var(--color-accent2)',
        success:  'var(--color-success)',
        warning:  'var(--color-warning)',
        danger:   'var(--color-danger)',
        muted:    'var(--color-muted)',
        text:     'var(--color-text)',
        text2:    'var(--color-text2)',
        'chart-grid': 'var(--color-chart-grid)',
        'chart-axis': 'var(--color-chart-axis)',
        'chart-in':   'var(--color-chart-in)',
        'chart-out':  'var(--color-chart-out)',
      },
      fontFamily: {
        sans: ['Noto Sans Thai', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"SF Mono"', '"Fira Code"', '"Cascadia Code"', 'monospace'],
        thai: ['Noto Sans Thai', '"TH Sarabun New"', 'Tahoma', 'sans-serif'],
      },
      fontSize: {
        'xs':   ['0.75rem',  { lineHeight: '1.5' }],   // 12px
        'sm':   ['0.8125rem', { lineHeight: '1.5' }],   // 13px
        'base': ['0.875rem', { lineHeight: '1.6' }],     // 14px
        'md':   ['1rem',     { lineHeight: '1.6' }],     // 16px
        'lg':   ['1.125rem', { lineHeight: '1.5' }],     // 18px
        'xl':   ['1.25rem',  { lineHeight: '1.4' }],     // 20px
        '2xl':  ['1.5rem',   { lineHeight: '1.35' }],    // 24px
        '3xl':  ['1.875rem', { lineHeight: '1.3' }],     // 30px
      },
      spacing: {
        '0.5': '2px',
        '1':   '4px',
        '1.5': '6px',
        '2':   '8px',
        '2.5': '10px',
        '3':   '12px',
        '3.5': '14px',
        '4':   '16px',
        '5':   '20px',
        '6':   '24px',
        '7':   '28px',
        '8':   '32px',
        '10':  '40px',
        '12':  '48px',
        '16':  '64px',
      },
      borderRadius: {
        'sm':  '4px',
        'DEFAULT': '6px',
        'md':  '8px',
        'lg':  '12px',
        'xl':  '16px',
        '2xl': '20px',
      },
      boxShadow: {
        'sm':   '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'DEFAULT': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
        'md':   '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
        'lg':   '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
        'card': '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
      },
    },
  },
  plugins: [],
}
