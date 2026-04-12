import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface CrossAccountTabProps {
  crossAccountSelected: string
  setCrossAccountSelected: (value: string) => void
  crossAccountTarget: string
  setCrossAccountTarget: (value: string) => void
  pathFrom: string
  setPathFrom: (value: string) => void
  pathTo: string
  setPathTo: (value: string) => void
  crossFlowData: any
  crossMatchData: any
  pathTraceData: any
  isPathTraceFetching: boolean
  refetchPathTrace: () => void
}

export function CrossAccountTab({
  crossAccountSelected,
  setCrossAccountSelected,
  crossAccountTarget,
  setCrossAccountTarget,
  pathFrom,
  setPathFrom,
  pathTo,
  setPathTo,
  crossFlowData,
  crossMatchData,
  pathTraceData,
  isPathTraceFetching,
  refetchPathTrace,
}: CrossAccountTabProps) {
  const { t } = useTranslation()

  return (
    <div className="space-y-4">
      {/* Account selector */}
      <Card className="space-y-3">
        <CardTitle>{t('investigation.crossAccount.selectAccount')}</CardTitle>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-muted font-semibold">{t('investigation.crossAccount.account')}</label>
            <input
              value={crossAccountSelected}
              onChange={e => { setCrossAccountSelected(e.target.value.replace(/\D/g, '')); setCrossAccountTarget('') }}
              placeholder="1234567890"
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none w-40"
            />
          </div>
          {crossAccountSelected && crossFlowData && (
            <div className="text-xs text-muted">
              <span className="text-text font-semibold">{crossFlowData.name || crossFlowData.account}</span>
              {crossFlowData.bank && <span className="ml-1">({crossFlowData.bank})</span>}
            </div>
          )}
        </div>
      </Card>

      {/* Flow summary */}
      {crossFlowData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Inbound */}
          <Card className="border-green-800/30">
            <CardTitle className="text-green-400 text-sm mb-2">
              {t('investigation.crossAccount.inbound')} ({crossFlowData.inbound_count}) — {t('results.flowGraph.totalIn')}: {Number(crossFlowData.total_in).toLocaleString('th-TH', {minimumFractionDigits: 2})}
            </CardTitle>
            <div className="max-h-60 overflow-y-auto">
              <table className="w-full text-xs">
                <tbody>
                  {(crossFlowData.inbound || []).map((f: any) => (
                    <tr
                      key={f.account}
                      className={`border-b border-border/30 hover:bg-green-900/10 cursor-pointer ${crossAccountTarget === f.account ? 'bg-green-900/20' : ''}`}
                      onClick={() => setCrossAccountTarget(f.account)}
                    >
                      <td className="px-2 py-1 font-mono text-green-400">{f.account}</td>
                      <td className="px-2 py-1 text-text2 truncate max-w-[120px]">{f.name}</td>
                      <td className="px-2 py-1 text-green-400 font-semibold text-right">{Number(f.total).toLocaleString('th-TH')}</td>
                      <td className="px-2 py-1 text-muted text-right">{f.count}x</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Outbound */}
          <Card className="border-red-800/30">
            <CardTitle className="text-red-400 text-sm mb-2">
              {t('investigation.crossAccount.outbound')} ({crossFlowData.outbound_count}) — {t('results.flowGraph.totalOut')}: {Number(crossFlowData.total_out).toLocaleString('th-TH', {minimumFractionDigits: 2})}
            </CardTitle>
            <div className="max-h-60 overflow-y-auto">
              <table className="w-full text-xs">
                <tbody>
                  {(crossFlowData.outbound || []).map((f: any) => (
                    <tr
                      key={f.account}
                      className={`border-b border-border/30 hover:bg-red-900/10 cursor-pointer ${crossAccountTarget === f.account ? 'bg-red-900/20' : ''}`}
                      onClick={() => setCrossAccountTarget(f.account)}
                    >
                      <td className="px-2 py-1 font-mono text-red-400">{f.account}</td>
                      <td className="px-2 py-1 text-text2 truncate max-w-[120px]">{f.name}</td>
                      <td className="px-2 py-1 text-red-400 font-semibold text-right">{Number(f.total).toLocaleString('th-TH')}</td>
                      <td className="px-2 py-1 text-muted text-right">{f.count}x</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* Pairwise transactions */}
      {crossAccountTarget && crossMatchData?.items?.length > 0 && (
        <Card>
          <CardTitle className="text-sm mb-2">
            {t('investigation.crossAccount.pairwise')}: {crossAccountSelected} ↔ {crossAccountTarget}
          </CardTitle>
          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-surface2">
                <tr className="border-b border-border text-muted">
                  <th className="px-2 py-1.5 text-left">{t('results.flowGraph.colDate')}</th>
                  <th className="px-2 py-1.5 text-right">{t('results.flowGraph.colAmount')}</th>
                  <th className="px-2 py-1.5 text-left">{t('results.flowGraph.colDir')}</th>
                  <th className="px-2 py-1.5 text-left">{t('results.flowGraph.colType')}</th>
                  <th className="px-2 py-1.5 text-left">{t('results.flowGraph.colDesc')}</th>
                </tr>
              </thead>
              <tbody>
                {crossMatchData.items.map((txn: any, i: number) => {
                  const isIn = txn.direction === 'IN'
                  return (
                    <tr key={i} className="border-b border-border/50 hover:bg-accent/5">
                      <td className="px-2 py-1 text-text2">{txn.date}</td>
                      <td className={`px-2 py-1 text-right font-mono font-medium ${isIn ? 'text-green-400' : 'text-red-400'}`}>
                        {isIn ? '+' : '-'}{Math.abs(txn.amount).toLocaleString('th-TH', {minimumFractionDigits: 2})}
                      </td>
                      <td className="px-2 py-1">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${isIn ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'}`}>
                          {txn.direction}
                        </span>
                      </td>
                      <td className="px-2 py-1 text-muted">{txn.transaction_type}</td>
                      <td className="px-2 py-1 text-text2 truncate max-w-[200px]">{txn.description}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Path Finder */}
      <Card className="space-y-3">
        <CardTitle className="text-sm">{t('investigation.crossAccount.pathFinder')}</CardTitle>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-muted font-semibold">{t('investigation.crossAccount.from')}</label>
            <input
              value={pathFrom}
              onChange={e => setPathFrom(e.target.value.replace(/\D/g, ''))}
              placeholder="1234567890"
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none w-36"
            />
          </div>
          <span className="text-muted text-lg pb-2">→</span>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase text-muted font-semibold">{t('investigation.crossAccount.to')}</label>
            <input
              value={pathTo}
              onChange={e => setPathTo(e.target.value.replace(/\D/g, ''))}
              placeholder="9876543210"
              className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none w-36"
            />
          </div>
          <Button
            variant="success"
            onClick={() => refetchPathTrace()}
            disabled={!pathFrom || !pathTo || isPathTraceFetching}
          >
            {isPathTraceFetching ? t('common.loading') : t('investigation.crossAccount.trace')}
          </Button>
        </div>

        {pathTraceData && (
          <div className="mt-3">
            {pathTraceData.found ? (
              <div className="space-y-2">
                <p className="text-xs text-green-400 font-semibold">
                  {t('investigation.crossAccount.pathsFound')}: {pathTraceData.path_count}
                </p>
                {pathTraceData.paths.map((path: any, pi: number) => (
                  <div key={pi} className="rounded-lg border border-border bg-surface2/50 p-3">
                    <div className="flex items-center gap-1 flex-wrap text-xs mb-2">
                      {path.hops.map((hop: string, hi: number) => (
                        <span key={hi} className="flex items-center gap-1">
                          <span className="px-2 py-0.5 rounded-full bg-accent/20 text-accent font-mono font-semibold">{hop}</span>
                          {hi < path.hops.length - 1 && <span className="text-red-400">→</span>}
                        </span>
                      ))}
                      <span className="ml-2 text-muted">({path.hop_count} {t('investigation.crossAccount.hops')})</span>
                    </div>
                    <div className="flex gap-3 text-[10px] text-muted">
                      {path.amounts.map((a: any, ai: number) => (
                        <span key={ai}>
                          {a.from.slice(-4)}→{a.to.slice(-4)}: <strong className="text-text">{Number(a.total).toLocaleString('th-TH')}</strong> ({a.count}x)
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted">{t('investigation.crossAccount.noPath')}</p>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
