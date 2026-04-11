import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { getDashboard } from '@/api'
import { Card, CardTitle } from '@/components/ui/card'
import { fmt, fmtDate } from '@/lib/utils'
import { FileText, Users, ArrowRightLeft, AlertTriangle, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

interface DashboardData {
  readonly file_count: number
  readonly account_count: number
  readonly transaction_count: number
  readonly alert_count: number
  readonly total_in: number
  readonly total_out: number
  readonly circulation: number
  readonly recent_activity: ReadonlyArray<{
    readonly status: string
    readonly bank: string
    readonly account: string
    readonly date: string
  }>
  readonly top_accounts: ReadonlyArray<{
    readonly account: string
    readonly name: string
    readonly bank: string
    readonly transaction_count: number
  }>
}

export function Dashboard() {
  const { t } = useTranslation()
  const { data, isLoading, isError } = useQuery<DashboardData>({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted text-sm">{t('common.loading')}</div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400 text-sm">{t('common.error')}</div>
      </div>
    )
  }

  const statCards = [
    { label: t('dashboard.stats.files'), value: data.file_count, icon: FileText, color: 'text-blue-400' },
    { label: t('dashboard.stats.accounts'), value: data.account_count, icon: Users, color: 'text-violet-400' },
    { label: t('dashboard.stats.transactions'), value: data.transaction_count, icon: ArrowRightLeft, color: 'text-sky-400' },
    { label: t('dashboard.stats.alerts'), value: data.alert_count, icon: AlertTriangle, color: 'text-amber-400' },
  ] as const

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-text">{t('dashboard.title')}</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="flex items-center gap-4">
            <div className={`p-2.5 rounded-lg bg-surface2 ${color}`}>
              <Icon size={20} />
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-muted font-semibold">{label}</div>
              <div className="text-2xl font-bold text-text">{value.toLocaleString()}</div>
            </div>
          </Card>
        ))}
      </div>

      {/* Flow summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardTitle>
            <TrendingUp size={16} className="text-emerald-400" />
            <span>{t('dashboard.flow.totalIn')}</span>
          </CardTitle>
          <div className="text-2xl font-bold text-emerald-400">{fmt(data.total_in)}</div>
        </Card>
        <Card>
          <CardTitle>
            <TrendingDown size={16} className="text-red-400" />
            <span>{t('dashboard.flow.totalOut')}</span>
          </CardTitle>
          <div className="text-2xl font-bold text-red-400">{fmt(data.total_out)}</div>
        </Card>
        <Card>
          <CardTitle>
            <RefreshCw size={16} className="text-sky-400" />
            <span>{t('dashboard.flow.circulation')}</span>
          </CardTitle>
          <div className="text-2xl font-bold text-sky-400">{fmt(data.circulation)}</div>
        </Card>
      </div>

      {/* Tables section */}
      <div className="grid grid-cols-2 gap-4">
        {/* Recent Activity */}
        <Card>
          <CardTitle>{t('dashboard.recentActivity.title')}</CardTitle>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted text-[11px] uppercase tracking-wide border-b border-border">
                  <th className="text-left py-2 pr-3 font-semibold">{t('dashboard.recentActivity.status')}</th>
                  <th className="text-left py-2 pr-3 font-semibold">{t('dashboard.recentActivity.bank')}</th>
                  <th className="text-left py-2 pr-3 font-semibold">{t('dashboard.recentActivity.account')}</th>
                  <th className="text-left py-2 font-semibold">{t('dashboard.recentActivity.date')}</th>
                </tr>
              </thead>
              <tbody>
                {(data.recent_activity ?? []).map((row, idx) => (
                  <tr key={idx} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                        row.status === 'success'
                          ? 'bg-emerald-500/15 text-emerald-400'
                          : row.status === 'error'
                            ? 'bg-red-500/15 text-red-400'
                            : 'bg-amber-500/15 text-amber-400'
                      }`}>
                        {row.status}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-text">{row.bank}</td>
                    <td className="py-2 pr-3 text-text font-mono text-xs">{row.account}</td>
                    <td className="py-2 text-muted">{fmtDate(row.date)}</td>
                  </tr>
                ))}
                {(!data.recent_activity || data.recent_activity.length === 0) && (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-muted text-xs">{t('dashboard.noData')}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Top Accounts */}
        <Card>
          <CardTitle>{t('dashboard.topAccounts.title')}</CardTitle>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted text-[11px] uppercase tracking-wide border-b border-border">
                  <th className="text-left py-2 pr-3 font-semibold">{t('dashboard.topAccounts.account')}</th>
                  <th className="text-left py-2 pr-3 font-semibold">{t('dashboard.topAccounts.name')}</th>
                  <th className="text-left py-2 pr-3 font-semibold">{t('dashboard.topAccounts.bank')}</th>
                  <th className="text-right py-2 font-semibold">{t('dashboard.topAccounts.txnCount')}</th>
                </tr>
              </thead>
              <tbody>
                {(data.top_accounts ?? []).map((row, idx) => (
                  <tr key={idx} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-3 text-text font-mono text-xs">{row.account}</td>
                    <td className="py-2 pr-3 text-text">{row.name || '—'}</td>
                    <td className="py-2 pr-3 text-muted">{row.bank}</td>
                    <td className="py-2 text-right text-text font-semibold">{row.transaction_count.toLocaleString()}</td>
                  </tr>
                ))}
                {(!data.top_accounts || data.top_accounts.length === 0) && (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-muted text-xs">{t('dashboard.noData')}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}
