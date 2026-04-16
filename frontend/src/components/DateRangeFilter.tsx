import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/card'
import { Calendar, RotateCcw } from 'lucide-react'

interface DateRangeFilterProps {
  /** Earliest date in the dataset (YYYY-MM-DD) */
  minDate: string
  /** Latest date in the dataset (YYYY-MM-DD) */
  maxDate: string
  /** Current filter start (null = no filter) */
  startDate: string | null
  /** Current filter end (null = no filter) */
  endDate: string | null
  /** Total items before filtering */
  totalCount?: number
  /** Filtered item count */
  filteredCount?: number
  onChange: (start: string | null, end: string | null) => void
}

type PresetKey = '7d' | '30d' | '90d' | 'all'

function subtractDays(dateStr: string, days: number): string {
  const d = new Date(dateStr)
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

export function DateRangeFilter({
  minDate,
  maxDate,
  startDate,
  endDate,
  totalCount,
  filteredCount,
  onChange,
}: DateRangeFilterProps) {
  const { t } = useTranslation()

  const presets: { key: PresetKey; label: string; start: string | null; end: string | null }[] = useMemo(() => {
    if (!maxDate) return []
    return [
      { key: '7d',  label: t('dateFilter.preset7d'),  start: subtractDays(maxDate, 7),  end: maxDate },
      { key: '30d', label: t('dateFilter.preset30d'), start: subtractDays(maxDate, 30), end: maxDate },
      { key: '90d', label: t('dateFilter.preset90d'), start: subtractDays(maxDate, 90), end: maxDate },
      { key: 'all', label: t('dateFilter.presetAll'), start: null,                       end: null },
    ]
  }, [maxDate, t])

  const activePreset = useMemo((): PresetKey | null => {
    if (!startDate && !endDate) return 'all'
    for (const p of presets) {
      if (p.start === startDate && p.end === endDate) return p.key
    }
    return null
  }, [startDate, endDate, presets])

  const isFiltered = startDate !== null || endDate !== null
  const showCount = typeof filteredCount === 'number' && typeof totalCount === 'number' && isFiltered

  return (
    <Card className="p-3">
      <div className="flex items-center gap-3 flex-wrap">
        {/* Label */}
        <div className="flex items-center gap-1.5 text-xs font-semibold text-muted whitespace-nowrap">
          <Calendar size={14} />
          {t('dateFilter.label')}
        </div>

        {/* Date inputs */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted">{t('dateFilter.from')}</span>
          <input
            type="date"
            value={startDate || ''}
            min={minDate}
            max={endDate || maxDate}
            onChange={e => onChange(e.target.value || null, endDate)}
            className="rounded-md border border-border bg-surface2 px-2 py-1 text-[11px] text-text outline-none focus:border-accent transition-colors"
          />
          <span className="text-[10px] text-muted">{t('dateFilter.to')}</span>
          <input
            type="date"
            value={endDate || ''}
            min={startDate || minDate}
            max={maxDate}
            onChange={e => onChange(startDate, e.target.value || null)}
            className="rounded-md border border-border bg-surface2 px-2 py-1 text-[11px] text-text outline-none focus:border-accent transition-colors"
          />
        </div>

        {/* Preset buttons */}
        <div className="flex gap-0.5 rounded-lg border border-border bg-surface2 p-0.5">
          {presets.map(p => (
            <button
              key={p.key}
              onClick={() => onChange(p.start, p.end)}
              className={`px-2 py-1 rounded-md text-[11px] font-medium cursor-pointer transition-colors ${
                activePreset === p.key
                  ? 'bg-accent/20 text-accent'
                  : 'text-muted hover:text-text'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Reset button */}
        {isFiltered && (
          <button
            onClick={() => onChange(null, null)}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium text-muted hover:text-text cursor-pointer transition-colors"
          >
            <RotateCcw size={10} />
            {t('dateFilter.reset')}
          </button>
        )}

        {/* Filtered count indicator */}
        {showCount && (
          <span className="ml-auto text-[10px] text-accent font-semibold">
            {t('dateFilter.showing')} {filteredCount?.toLocaleString()} / {totalCount?.toLocaleString()}
          </span>
        )}
      </div>
    </Card>
  )
}
