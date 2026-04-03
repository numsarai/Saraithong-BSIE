/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#0d1117',
        surface:  '#161b22',
        surface2: '#21262d',
        surface3: '#30363d',
        border:   '#30363d',
        accent:   '#58a6ff',
        accent2:  '#388bfd',
        success:  '#3fb950',
        warning:  '#d29922',
        danger:   '#f85149',
        muted:    '#8b949e',
        text:     '#e6edf3',
        text2:    '#c9d1d9',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"SF Mono"', '"Fira Code"', '"Cascadia Code"', 'monospace'],
      },
    },
  },
  plugins: [],
}

