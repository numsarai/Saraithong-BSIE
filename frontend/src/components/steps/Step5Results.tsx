import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getResults, saveOverride } from '@/api'
import { useStore } from '@/store'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { fmt } from '@/lib/utils'
import { toast } from 'sonner'
import { Download, RotateCcw } from 'lucide-react'

type OverrideState = { tid: string; from: string; to: string } | null

export function Step5Results() {
  const { results, account, currentTab, setCurrentTab, reset } = useStore()
  const meta = results?.meta || {}
  const [page, setPage]       = useState(1)
  const [override, setOverride] = useState<OverrideState>(null)
  const [ovForm, setOvForm]   = useState({ from: '', to: '', reason: '', by: 'analyst' })

  const { data: txnData, refetch } = useQuery({
    queryKey: ['results', account, page],
    queryFn: () => getResults(account, page, 100),
    enabled: !!account,
  })

  const rows       = txnData?.rows   || []
  const total      = txnData?.total  || 0
  const totalPages = Math.ceil(total / 100) || 1

  const dlBase  = `/api/download/${account}`
  const downloads = [
    { label: 'Report (.xlsx)',        file: 'processed/report.xlsx' },
    { label: 'Transactions (.csv)',   file: 'processed/transactions.csv' },
    { label: 'Entities (.csv)',       file: 'processed/entities.csv' },
    { label: 'Entities (.xlsx)',      file: 'processed/entities.xlsx' },
    { label: 'Links (.csv)',          file: 'processed/links.csv' },
    { label: 'Original (.xlsx)',      file: 'raw/original.xlsx' },
    { label: 'Metadata (.json)',      file: 'meta.json' },
  ]

  const statCards = [
    { label: 'Transactions',   value: String(meta.num_transactions ?? total),          color: '' },
    { label: 'Total IN',       value: `฿${fmt(meta.total_in  || 0)}`,                  color: 'text-success' },
    { label: 'Total OUT',      value: `฿${fmt(meta.total_out || 0)}`,                  color: 'text-danger' },
    { label: 'Circulation',    value: `฿${fmt(meta.total_circulation || 0)}`,           color: 'text-accent' },
    { label: 'Date Range',     value: meta.date_range || '—',                           color: '' },
    { label: 'Unknown CPs',    value: String(meta.num_unknown ?? '—'),                  color: '' },
    { label: 'Partial Accts',  value: String(meta.num_partial_accounts ?? '—'),         color: '' },
  ]

  const openOverride = (row: any) => {
    setOverride({ tid: row.transaction_id, from: row.from_account || '', to: row.to_account || '' })
    setOvForm({ from: row.from_account || '', to: row.to_account || '', reason: '', by: 'analyst' })
  }

  const handleSaveOverride = async () => {
    if (!override) return
    try {
      await saveOverride({
        transaction_id: override.tid,
        from_account: ovForm.from,
        to_account: ovForm.to,
        reason: ovForm.reason,
        override_by: ovForm.by,
      })
      toast.success('Override saved')
      setOverride(null)
      refetch()
    } catch (e: any) { toast.error(e.message) }
  }

  const TABS = ['transactions', 'entities', 'links'] as const

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-text">Results</h2>
          <p className="text-muted text-sm">{account} · {meta.bank || ''} · {total} transactions</p>
        </div>
        <Button variant="ghost" size="sm" onClick={reset}>
          <RotateCcw size={13} />Process Another File
        </Button>
      </div>

      {/* Downloads */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-2">
        {downloads.map(d => (
          <a
            key={d.file}
            href={`${dlBase}/${d.file}`}
            download
            className="flex items-center gap-2 px-3 py-2.5 bg-surface2 border border-border rounded-lg text-accent text-sm hover:border-accent transition-all"
          >
            <Download size={13} />{d.label}
          </a>
        ))}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(130px,1fr))] gap-3">
        {statCards.map(s => (
          <div key={s.label} className="bg-surface border border-border rounded-xl p-4">
            <div className="text-[11px] uppercase text-muted mb-1 font-semibold">{s.label}</div>
            <div className={`text-xl font-bold ${s.color || 'text-text'}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-border">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setCurrentTab(tab)}
            className={[
              'px-4 py-2 text-sm font-medium capitalize transition-all border-b-2 -mb-px',
              currentTab === tab
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-text2',
            ].join(' ')}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Transactions tab */}
      {currentTab === 'transactions' && (
        <div className="space-y-3">
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-xs border-collapse" style={{ minWidth: 900 }}>
              <thead>
                <tr className="bg-surface2">
                  {['ID','Date','Amount','Dir','Type','Conf','CP Account','CP Name','Description','From','To',''].map((h, idx) => (
                    <th key={idx} className="py-2 px-2 text-left text-[10px] uppercase text-muted border-b border-border font-semibold whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any) => (
                  <tr
                    key={row.transaction_id}
                    className={['border-b border-border/40 hover:bg-accent/[0.04] transition-colors', row.is_overridden ? 'bg-success/5' : ''].join(' ')}
                  >
                    <td className="py-1.5 px-2 font-mono text-muted">{row.transaction_id}</td>
                    <td className="py-1.5 px-2 text-text2 whitespace-nowrap">{row.date}</td>
                    <td className={`py-1.5 px-2 font-mono font-bold ${row.direction === 'IN' ? 'text-success' : 'text-danger'}`}>
                      {row.direction === 'IN' ? '+' : '-'}{fmt(Math.abs(row.amount || 0))}
                    </td>
                    <td className="py-1.5 px-2">
                      <Badge variant={row.direction === 'IN' ? 'green' : 'red'}>{row.direction}</Badge>
                    </td>
                    <td className="py-1.5 px-2 text-text2">{row.transaction_type}</td>
                    <td className="py-1.5 px-2 text-muted">{Math.round((row.confidence || 0) * 100)}%</td>
                    <td className="py-1.5 px-2 font-mono text-text2 max-w-[120px] truncate">{row.counterparty_account || '—'}</td>
                    <td className="py-1.5 px-2 text-text2 max-w-[100px] truncate">{row.counterparty_name || '—'}</td>
                    <td className="py-1.5 px-2 text-muted max-w-[150px] truncate">{row.description}</td>
                    <td className="py-1.5 px-2 font-mono text-text2 max-w-[100px] truncate">{row.from_account || '—'}</td>
                    <td className="py-1.5 px-2 font-mono text-text2 max-w-[100px] truncate">{row.to_account || '—'}</td>
                    <td className="py-1.5 px-2">
                      <button
                        onClick={() => openOverride(row)}
                        className="text-[10px] text-accent border border-accent/30 rounded px-1.5 py-0.5 hover:bg-accent/10 transition-colors"
                      >
                        {row.is_overridden ? 'Edit' : 'Override'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          <div className="flex items-center gap-2 text-sm text-muted">
            <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Prev</Button>
            <span>Page {page} of {totalPages} · {total} rows</span>
            <Button size="sm" variant="ghost" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</Button>
          </div>
        </div>
      )}

      {/* Entities tab */}
      {currentTab === 'entities' && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-surface2">
                {['Entity ID','Type','Value','Count','First Seen','Last Seen'].map(h => (
                  <th key={h} className="py-2 px-3 text-left text-[10px] uppercase text-muted border-b border-border font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(results?.entities || []).map((e: any) => (
                <tr key={e.entity_id} className="border-b border-border/40 hover:bg-accent/[0.04]">
                  <td className="py-1.5 px-3 font-mono text-muted text-[10px]">{e.entity_id}</td>
                  <td className="py-1.5 px-3"><Badge variant="blue">{e.entity_type}</Badge></td>
                  <td className="py-1.5 px-3 text-text2">{e.value}</td>
                  <td className="py-1.5 px-3 text-text2">{e.count}</td>
                  <td className="py-1.5 px-3 text-muted">{e.first_seen}</td>
                  <td className="py-1.5 px-3 text-muted">{e.last_seen}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Links tab */}
      {currentTab === 'links' && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-surface2">
                {['Txn ID','From','To','Amount','Date','Type'].map(h => (
                  <th key={h} className="py-2 px-3 text-left text-[10px] uppercase text-muted border-b border-border font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(results?.links || []).map((l: any, i: number) => (
                <tr key={i} className="border-b border-border/40 hover:bg-accent/[0.04]">
                  <td className="py-1.5 px-3 font-mono text-muted text-[10px]">{l.transaction_id}</td>
                  <td className="py-1.5 px-3 font-mono text-text2">{l.from_account}</td>
                  <td className="py-1.5 px-3 font-mono text-text2">{l.to_account}</td>
                  <td className="py-1.5 px-3 text-success font-mono">฿{fmt(Math.abs(l.amount || 0))}</td>
                  <td className="py-1.5 px-3 text-muted">{l.date}</td>
                  <td className="py-1.5 px-3 text-text2">{l.transaction_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Override Modal */}
      {override && (
        <div
          className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4"
          onClick={() => setOverride(null)}
        >
          <div
            className="bg-surface border border-border rounded-xl p-6 w-full max-w-[500px] shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-base font-bold mb-4 text-text">Override Relationship</h3>
            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] uppercase text-muted font-semibold">Transaction ID</label>
                <input
                  value={override.tid} readOnly
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-muted"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                {(['from','to'] as const).map(k => (
                  <div key={k} className="flex flex-col gap-1">
                    <label className="text-[11px] uppercase text-muted font-semibold">{k === 'from' ? 'FROM' : 'TO'} Account</label>
                    <input
                      value={ovForm[k]}
                      onChange={e => setOvForm(f => ({ ...f, [k]: e.target.value }))}
                      className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
                    />
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] uppercase text-muted font-semibold">Reason</label>
                <input
                  value={ovForm.reason}
                  onChange={e => setOvForm(f => ({ ...f, reason: e.target.value }))}
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] uppercase text-muted font-semibold">Override By</label>
                <input
                  value={ovForm.by}
                  onChange={e => setOvForm(f => ({ ...f, by: e.target.value }))}
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-accent outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <Button variant="ghost" onClick={() => setOverride(null)}>Cancel</Button>
              <Button variant="primary" onClick={handleSaveOverride}>Save Override</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
