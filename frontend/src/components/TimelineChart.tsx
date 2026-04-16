import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell, ScatterChart, Scatter, ZAxis,
} from 'recharts'
import { Card, CardTitle } from '@/components/ui/card'
import { BarChart2, Circle, Calendar } from 'lucide-react'

type Granularity = 'day' | 'week' | 'month'
type ViewMode = 'bar' | 'dot'

interface TxnRow {
  date?: string
  transaction_datetime?: string
  posted_date?: string
  amount?: number | string
  direction?: string
  transaction_type?: string
  counterparty_name_normalized?: string
  counterparty_name?: string
  counterparty_account_normalized?: string
  description_normalized?: string
  description?: string
}

interface TimelineChartProps {
  transactions: TxnRow[]
  title?: string
  onSelectDate?: (date: string) => void
}

interface Bucket {
  label: string
  dateKey: string
  inAmount: number
  outAmount: number
  inCount: number
  outCount: number
}

function parseDate(row: TxnRow): string {
  const raw = row.transaction_datetime || row.posted_date || row.date || ''
  return String(raw).slice(0, 10) // YYYY-MM-DD
}

function toWeekKey(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(d)
  monday.setDate(diff)
  return monday.toISOString().slice(0, 10)
}

function toMonthKey(dateStr: string): string {
  return dateStr.slice(0, 7) // YYYY-MM
}

function bucketize(txns: TxnRow[], granularity: Granularity): Bucket[] {
  const map = new Map<string, Bucket>()

  for (const txn of txns) {
    const dateStr = parseDate(txn)
    if (!dateStr || dateStr.length < 7) continue

    let key: string
    if (granularity === 'week') key = toWeekKey(dateStr)
    else if (granularity === 'month') key = toMonthKey(dateStr)
    else key = dateStr

    const amount = Math.abs(parseFloat(String(txn.amount)) || 0)
    const dir = String(txn.direction || '').toUpperCase()

    const bucket = map.get(key) || { label: key, dateKey: key, inAmount: 0, outAmount: 0, inCount: 0, outCount: 0 }
    if (dir === 'IN') {
      bucket.inAmount += amount
      bucket.inCount += 1
    } else if (dir === 'OUT') {
      bucket.outAmount += amount
      bucket.outCount += 1
    }
    map.set(key, bucket)
  }

  return Array.from(map.values()).sort((a, b) => a.dateKey.localeCompare(b.dateKey))
}

function formatLabel(key: string, gran: Granularity): string {
  if (gran === 'month') {
    const [y, m] = key.split('-')
    return `${m}/${y.slice(2)}`
  }
  if (gran === 'week') return key.slice(5) // MM-DD
  return key.slice(5) // MM-DD
}

function formatAmount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toFixed(0)
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const data = payload[0]?.payload as Bucket
  if (!data) return null
  return (
    <div className="rounded-lg border border-border bg-surface2 px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-text mb-1">{data.dateKey}</p>
      <p className="text-green-400">IN: {data.inCount} txns &middot; {formatAmount(data.inAmount)} THB</p>
      <p className="text-red-400">OUT: {data.outCount} txns &middot; {formatAmount(data.outAmount)} THB</p>
    </div>
  )
}

interface DotData {
  x: number
  y: number
  size: number
  direction: string
  amount: number
  date: string
  cp: string
  desc: string
}

/** Read chart colors from CSS variables so Recharts adapts to light/dark theme. */
function useChartColors() {
  const [colors, setColors] = useState({ grid: '#334155', axis: '#64748b', in: '#16a34a', out: '#dc2626' })
  useEffect(() => {
    const update = () => {
      const s = getComputedStyle(document.documentElement)
      setColors({
        grid: s.getPropertyValue('--color-chart-grid').trim() || '#334155',
        axis: s.getPropertyValue('--color-chart-axis').trim() || '#64748b',
        in:   s.getPropertyValue('--color-chart-in').trim()   || '#16a34a',
        out:  s.getPropertyValue('--color-chart-out').trim()  || '#dc2626',
      })
    }
    update()
    const obs = new MutationObserver(update)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return colors
}

export function TimelineChart({ transactions, title, onSelectDate }: TimelineChartProps) {
  const { t } = useTranslation()
  const chartColors = useChartColors()
  const [granularity, setGranularity] = useState<Granularity>('day')
  const [viewMode, setViewMode] = useState<ViewMode>('bar')
  const [selectedDot, setSelectedDot] = useState<DotData | null>(null)

  const buckets = useMemo(() => bucketize(transactions, granularity), [transactions, granularity])

  // Prepare chart data: outAmount shown as negative for dual-sided bar
  const chartData = useMemo(() =>
    buckets.map(b => ({
      ...b,
      label: formatLabel(b.dateKey, granularity),
      outNeg: -b.outAmount,
    })),
    [buckets, granularity],
  )

  // Dot timeline data
  const dotData = useMemo((): DotData[] => {
    if (viewMode !== 'dot') return []
    const sorted = [...transactions]
      .filter(t => parseDate(t).length >= 10)
      .sort((a, b) => parseDate(a).localeCompare(parseDate(b)))

    return sorted.map((txn, i) => {
      const amount = Math.abs(parseFloat(String(txn.amount)) || 0)
      return {
        x: i,
        y: String(txn.direction || '').toUpperCase() === 'IN' ? 1 : -1,
        size: Math.max(20, Math.min(500, amount / 100)),
        direction: String(txn.direction || '').toUpperCase(),
        amount,
        date: parseDate(txn),
        cp: String(txn.counterparty_name_normalized || txn.counterparty_name || txn.counterparty_account_normalized || ''),
        desc: String(txn.description_normalized || txn.description || ''),
      }
    })
  }, [transactions, viewMode])

  if (transactions.length === 0) return null

  const displayTitle = title || t('results.timeline.title')

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <CardTitle className="text-text">{displayTitle}</CardTitle>
        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex gap-0.5 rounded-lg border border-border bg-surface2 p-0.5">
            <button
              onClick={() => setViewMode('bar')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium cursor-pointer transition-colors ${viewMode === 'bar' ? 'bg-accent/20 text-accent' : 'text-muted hover:text-text'}`}
            >
              <BarChart2 size={12} />
              {t('results.timeline.barMode')}
            </button>
            <button
              onClick={() => setViewMode('dot')}
              className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium cursor-pointer transition-colors ${viewMode === 'dot' ? 'bg-accent/20 text-accent' : 'text-muted hover:text-text'}`}
            >
              <Circle size={12} />
              {t('results.timeline.dotMode')}
            </button>
          </div>

          {/* Granularity toggle (bar mode only) */}
          {viewMode === 'bar' && (
            <div className="flex gap-0.5 rounded-lg border border-border bg-surface2 p-0.5">
              {(['day', 'week', 'month'] as Granularity[]).map(g => (
                <button
                  key={g}
                  onClick={() => setGranularity(g)}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium cursor-pointer transition-colors ${granularity === g ? 'bg-accent/20 text-accent' : 'text-muted hover:text-text'}`}
                >
                  <Calendar size={10} />
                  {t(`results.timeline.${g}`)}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {viewMode === 'bar' ? (
        <div className="w-full" style={{ height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 10, right: 10, left: 10, bottom: 5 }}
              stackOffset="sign"
              onClick={(data: any) => {
                if (data?.activePayload?.[0]?.payload?.dateKey && onSelectDate) {
                  onSelectDate(data.activePayload[0].payload.dateKey)
                }
              }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: chartColors.axis }}
                interval={Math.max(0, Math.floor(chartData.length / 20))}
              />
              <YAxis
                tick={{ fontSize: 10, fill: chartColors.axis }}
                tickFormatter={formatAmount}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="inAmount" fill={chartColors.in} radius={[2, 2, 0, 0]} name={t('results.timeline.in')} />
              <Bar dataKey="outNeg" fill={chartColors.out} radius={[0, 0, 2, 2]} name={t('results.timeline.out')} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="w-full overflow-x-auto" style={{ height: 240 }}>
          <ResponsiveContainer width={Math.max(600, dotData.length * 4)} height="100%">
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
              <XAxis
                dataKey="x"
                type="number"
                tick={false}
                axisLine={{ stroke: chartColors.axis }}
              />
              <YAxis
                dataKey="y"
                type="number"
                domain={[-2, 2]}
                tick={false}
                axisLine={{ stroke: chartColors.axis }}
              />
              <ZAxis dataKey="size" range={[20, 500]} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0].payload as DotData
                  return (
                    <div className="rounded-lg border border-border bg-surface2 px-3 py-2 text-xs shadow-lg">
                      <p className="font-semibold text-text">{d.date}</p>
                      <p className={d.direction === 'IN' ? 'text-green-400' : 'text-red-400'}>
                        {d.direction} {formatAmount(d.amount)} THB
                      </p>
                      {d.cp && <p className="text-muted">{d.cp}</p>}
                      {d.desc && <p className="text-muted truncate max-w-[200px]">{d.desc}</p>}
                    </div>
                  )
                }}
              />
              <Scatter data={dotData} onClick={(data) => setSelectedDot(data as any)}>
                {dotData.map((d, i) => (
                  <Cell key={i} fill={d.direction === 'IN' ? chartColors.in : chartColors.out} fillOpacity={0.7} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>

          {selectedDot && (
            <div className="mt-2 rounded-md border border-accent/30 bg-surface2 px-3 py-2 text-xs flex items-center gap-4">
              <span className="font-semibold text-text">{selectedDot.date}</span>
              <span className={selectedDot.direction === 'IN' ? 'text-green-400' : 'text-red-400'}>
                {selectedDot.direction === 'IN' ? '+' : '-'}{formatAmount(selectedDot.amount)} THB
              </span>
              {selectedDot.cp && <span className="text-muted">{selectedDot.cp}</span>}
              {selectedDot.desc && <span className="text-muted truncate max-w-[200px]">{selectedDot.desc}</span>}
              <button onClick={() => setSelectedDot(null)} className="ml-auto text-muted hover:text-text cursor-pointer">&times;</button>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
