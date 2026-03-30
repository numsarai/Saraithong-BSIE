import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
export function fmt(n: number) {
  return new Intl.NumberFormat('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)
}

const BANGKOK_DATE_FORMATTER = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Bangkok',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

function padDisplayDate(day: string, month: string, year: string) {
  return `${day.padStart(2, '0')} ${month.padStart(2, '0')} ${year}`
}

export function fmtDate(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return BANGKOK_DATE_FORMATTER.format(value).replaceAll('/', ' ')
  }

  const text = String(value).trim()
  if (!text) return '—'

  const thaiDisplayMatch = text.match(/^(\d{1,2})[\/\-\s](\d{1,2})[\/\-\s](\d{4})$/)
  if (thaiDisplayMatch) {
    return padDisplayDate(thaiDisplayMatch[1], thaiDisplayMatch[2], thaiDisplayMatch[3])
  }

  const isoDateMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (isoDateMatch) {
    return padDisplayDate(isoDateMatch[3], isoDateMatch[2], isoDateMatch[1])
  }

  const parsed = new Date(text)
  if (!Number.isNaN(parsed.getTime())) {
    return BANGKOK_DATE_FORMATTER.format(parsed).replaceAll('/', ' ')
  }

  return text
}

export function fmtDateRange(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  const text = String(value).trim()
  if (!text) return '—'

  const rangeMatch = text.match(/^(.+?)\s+to\s+(.+)$/i)
  if (!rangeMatch) return fmtDate(text)
  return `${fmtDate(rangeMatch[1])} to ${fmtDate(rangeMatch[2])}`
}
