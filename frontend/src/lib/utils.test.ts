import { describe, expect, it } from 'vitest'
import { fmtDate, fmtDateRange } from './utils'

describe('fmtDate', () => {
  it('formats ISO date to DD MM YYYY', () => {
    expect(fmtDate('2026-03-30')).toBe('30 03 2026')
  })

  it('formats ISO datetime in Bangkok timezone', () => {
    expect(fmtDate('2026-03-30T23:30:00Z')).toBe('31 03 2026')
  })

  it('preserves DD MM YYYY style while normalizing separators', () => {
    expect(fmtDate('30/03/2026')).toBe('30 03 2026')
  })
})

describe('fmtDateRange', () => {
  it('formats date ranges for table display', () => {
    expect(fmtDateRange('2026-03-01 to 2026-03-10')).toBe('01 03 2026 to 10 03 2026')
  })
})
