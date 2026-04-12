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
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"SF Mono"', '"Fira Code"', '"Cascadia Code"', 'monospace'],
      },
    },
  },
  plugins: [],
}
