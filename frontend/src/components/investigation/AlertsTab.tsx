import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { reviewAlert as reviewAlertApi } from '@/api'

function StatCard({ label, value, tone = 'text-text' }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface px-4 py-3">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className={`text-lg font-bold ${tone}`}>{value}</div>
    </div>
  )
}

interface AlertsTabProps {
  alertItems: any[]
  alertSummary: any
  operatorName: string
  isLoading: boolean
  refetchAlerts: () => void
  refetchAlertSummary: () => void
}

export function AlertsTab({
  alertItems,
  alertSummary,
  operatorName,
  isLoading,
  refetchAlerts,
  refetchAlertSummary,
}: AlertsTabProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-3">
        <StatCard label={t('investigation.alerts.total')} value={alertSummary.total ?? 0} />
        <div className="rounded-xl border border-red-800/40 bg-red-900/20 px-3 py-2 text-center">
          <div className="text-lg font-bold text-red-400">{alertSummary.critical_count ?? 0}</div>
          <div className="text-[10px] text-red-400/70 uppercase font-semibold">{t('investigation.alerts.critical')}</div>
        </div>
        <div className="rounded-xl border border-orange-800/40 bg-orange-900/20 px-3 py-2 text-center">
          <div className="text-lg font-bold text-orange-400">{alertSummary.high_count ?? 0}</div>
          <div className="text-[10px] text-orange-400/70 uppercase font-semibold">{t('investigation.alerts.high')}</div>
        </div>
        <StatCard label={t('investigation.alerts.newAlerts')} value={alertSummary.new_count ?? 0} />
      </div>

      {/* Alert list */}
      {alertItems.length > 0 ? (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-muted text-left">
                  <th className="px-2 py-2 font-semibold">{t('investigation.alerts.severity')}</th>
                  <th className="px-2 py-2 font-semibold">{t('investigation.alerts.ruleType')}</th>
                  <th className="px-2 py-2 font-semibold">{t('investigation.alerts.summary')}</th>
                  <th className="px-2 py-2 font-semibold">{t('investigation.alerts.confidence')}</th>
                  <th className="px-2 py-2 font-semibold">{t('investigation.alerts.status')}</th>
                  <th className="px-2 py-2 font-semibold">{t('investigation.alerts.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {alertItems.map((alert: any) => {
                  const sevColor = alert.severity === 'critical' ? 'text-red-400 bg-red-900/30'
                    : alert.severity === 'high' ? 'text-orange-400 bg-orange-900/30'
                    : alert.severity === 'medium' ? 'text-yellow-400 bg-yellow-900/30'
                    : 'text-blue-400 bg-blue-900/30'
                  const statusColor = alert.status === 'new' ? 'text-red-400'
                    : alert.status === 'acknowledged' ? 'text-yellow-400'
                    : 'text-green-400'
                  return (
                    <tr key={alert.id} className="border-b border-border/50 hover:bg-accent/5">
                      <td className="px-2 py-1.5">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${sevColor}`}>
                          {alert.severity}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 text-text2 font-mono">{alert.rule_type}</td>
                      <td className="px-2 py-1.5 text-text2 max-w-[300px] truncate">{alert.summary}</td>
                      <td className="px-2 py-1.5 text-muted">{(alert.confidence * 100).toFixed(0)}%</td>
                      <td className="px-2 py-1.5">
                        <span className={`font-semibold ${statusColor}`}>{alert.status}</span>
                      </td>
                      <td className="px-2 py-1.5">
                        {alert.status === 'new' && (
                          <Button
                            variant="ghost"
                            onClick={async () => {
                              await reviewAlertApi(alert.id, 'acknowledged', operatorName)
                              refetchAlerts()
                              refetchAlertSummary()
                            }}
                          >
                            {t('investigation.alerts.acknowledge')}
                          </Button>
                        )}
                        {alert.status === 'acknowledged' && (
                          <Button
                            variant="ghost"
                            onClick={async () => {
                              await reviewAlertApi(alert.id, 'resolved', operatorName)
                              refetchAlerts()
                              refetchAlertSummary()
                            }}
                          >
                            {t('investigation.alerts.resolve')}
                          </Button>
                        )}
                        {alert.status === 'resolved' && (
                          <span className="text-green-400 text-[10px]">{t('investigation.alerts.resolved')}</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card className="p-8 text-center text-muted text-sm">
          {isLoading ? t('common.loading') : t('investigation.alerts.noAlerts')}
        </Card>
      )}
    </div>
  )
}
