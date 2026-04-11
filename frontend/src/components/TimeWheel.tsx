import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/card'

interface TimeWheelProps {
  transactions: any[]
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const HOURS = Array.from({ length: 24 }, (_, i) => i)

function parseHourDay(txn: any): { hour: number; day: number } | null {
  const dt = txn.transaction_datetime || txn.date || ''
  const dateObj = new Date(dt)
  if (isNaN(dateObj.getTime())) return null
  return { hour: dateObj.getHours(), day: dateObj.getDay() }
}

export function TimeWheel({ transactions }: TimeWheelProps) {
  const { t } = useTranslation()
  // mode reserved for future use (hour/day/week toggle)

  // Build heatmap: hour × day
  const heatmap = useMemo(() => {
    const grid: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0))
    const hourTotals = Array(24).fill(0)
    const dayTotals = Array(7).fill(0)

    for (const txn of transactions) {
      const parsed = parseHourDay(txn)
      if (!parsed) continue
      const amount = Math.abs(parseFloat(txn.amount) || 0)
      grid[parsed.day][parsed.hour] += amount
      hourTotals[parsed.hour] += amount
      dayTotals[parsed.day] += amount
    }

    const maxVal = Math.max(...grid.flat(), 1)
    return { grid, hourTotals, dayTotals, maxVal }
  }, [transactions])

  if (transactions.length === 0) return null

  const cellColor = (val: number) => {
    if (val === 0) return 'bg-surface2'
    const intensity = Math.min(val / heatmap.maxVal, 1)
    if (intensity > 0.7) return 'bg-red-600'
    if (intensity > 0.4) return 'bg-orange-500'
    if (intensity > 0.15) return 'bg-yellow-500'
    return 'bg-green-700'
  }

  const formatVal = (v: number) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`
    return v > 0 ? v.toFixed(0) : ''
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <CardTitle className="text-text">{t('timeWheel.title')}</CardTitle>
        <div className="flex gap-1 text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-green-700 text-white">Low</span>
          <span className="px-1.5 py-0.5 rounded bg-yellow-500 text-black">Med</span>
          <span className="px-1.5 py-0.5 rounded bg-orange-500 text-white">High</span>
          <span className="px-1.5 py-0.5 rounded bg-red-600 text-white">Very High</span>
        </div>
      </div>

      {/* Hour × Day heatmap grid */}
      <div className="overflow-x-auto">
        <table className="w-full text-[9px]">
          <thead>
            <tr>
              <th className="px-1 py-1 text-muted text-left w-10"></th>
              {HOURS.map(h => (
                <th key={h} className="px-0.5 py-1 text-muted text-center w-6">{String(h).padStart(2, '0')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {DAYS.map((day, di) => (
              <tr key={day}>
                <td className="px-1 py-0.5 text-muted font-semibold">{day}</td>
                {HOURS.map(h => {
                  const val = heatmap.grid[di][h]
                  return (
                    <td
                      key={h}
                      className={`px-0.5 py-0.5 text-center rounded-sm ${cellColor(val)}`}
                      title={`${day} ${String(h).padStart(2, '0')}:00 — ${formatVal(val)} THB`}
                    >
                      <div className="w-4 h-4 rounded-sm" />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Hour summary bar */}
      <div className="mt-3">
        <p className="text-[10px] text-muted mb-1 font-semibold">{t('timeWheel.byHour')}</p>
        <div className="flex gap-px h-8">
          {HOURS.map(h => {
            const val = heatmap.hourTotals[h]
            const height = heatmap.maxVal > 0 ? Math.max(2, (val / Math.max(...heatmap.hourTotals, 1)) * 32) : 2
            return (
              <div
                key={h}
                className="flex-1 flex items-end justify-center"
                title={`${String(h).padStart(2, '0')}:00 — ${formatVal(val)} THB`}
              >
                <div className="w-full bg-accent/60 rounded-t-sm" style={{ height: `${height}px` }} />
              </div>
            )
          })}
        </div>
        <div className="flex gap-px text-[8px] text-muted">
          {HOURS.map(h => (
            <div key={h} className="flex-1 text-center">{h % 6 === 0 ? `${h}h` : ''}</div>
          ))}
        </div>
      </div>

      {/* Day summary */}
      <div className="mt-3">
        <p className="text-[10px] text-muted mb-1 font-semibold">{t('timeWheel.byDay')}</p>
        <div className="flex gap-1">
          {DAYS.map((day, di) => {
            const val = heatmap.dayTotals[di]
            const pct = Math.max(...heatmap.dayTotals, 1)
            return (
              <div key={day} className="flex-1 text-center">
                <div className="bg-surface2 rounded-sm overflow-hidden h-6 flex items-end">
                  <div
                    className="w-full bg-accent/50 rounded-t-sm"
                    style={{ height: `${Math.max(2, (val / pct) * 24)}px` }}
                  />
                </div>
                <span className="text-[8px] text-muted">{day}</span>
              </div>
            )
          })}
        </div>
      </div>
    </Card>
  )
}
