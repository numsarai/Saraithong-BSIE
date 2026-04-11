import { useEffect, useRef, useMemo, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import cytoscape from 'cytoscape'
import { Card, CardTitle } from '@/components/ui/card'
import { Circle, Maximize2, Minimize2, X } from 'lucide-react'

interface FlowGraphProps {
  account: string
  bankKey: string
  rows: any[]
}

interface AggEdge {
  counterparty: string
  counterpartyName: string
  direction: 'IN' | 'OUT'
  totalAmount: number
  count: number
}

function formatAmount(n: number): string {
  return Math.abs(n).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/**
 * Try to load pre-aggregated edges from the CSV export.
 * Falls back to aggregating from raw transaction rows.
 */
async function fetchAggregatedEdges(account: string): Promise<AggEdge[] | null> {
  try {
    const res = await fetch(`/api/download/${account}/processed/aggregated_edges.csv`)
    if (!res.ok) return null
    const text = await res.text()
    const lines = text.split('\n').filter(l => l.trim())
    if (lines.length < 2) return null

    const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
    const fromIdx = headers.indexOf('from_node_id')
    const toIdx = headers.indexOf('to_node_id')
    const typeIdx = headers.indexOf('edge_type')
    const countIdx = headers.indexOf('transaction_count')
    const amountIdx = headers.indexOf('total_amount_abs')
    const labelIdx = headers.indexOf('label')
    if (fromIdx < 0 || toIdx < 0) return null

    const subjectNode = `ACCOUNT:${account}`
    const edges: AggEdge[] = []

    for (let i = 1; i < lines.length; i++) {
      // Simple CSV parse (handles quoted fields with commas)
      const row = parseCsvLine(lines[i])
      if (!row || row.length < Math.max(fromIdx, toIdx, countIdx, amountIdx) + 1) continue

      const fromNode = row[fromIdx]
      const toNode = row[toIdx]
      const edgeType = typeIdx >= 0 ? row[typeIdx] : ''
      const count = countIdx >= 0 ? parseInt(row[countIdx]) || 1 : 1
      const amount = amountIdx >= 0 ? parseFloat(row[amountIdx]) || 0 : 0

      let cp: string
      let dir: 'IN' | 'OUT'

      if (edgeType === 'RECEIVED_FROM' || toNode === subjectNode) {
        cp = fromNode.replace('ACCOUNT:', '')
        dir = 'IN'
      } else if (edgeType === 'SENT_TO' || fromNode === subjectNode) {
        cp = toNode.replace('ACCOUNT:', '')
        dir = 'OUT'
      } else {
        continue
      }

      if (!cp || cp === account) continue

      // Extract name from label if available (e.g. "Sent To (3 transactions)")
      const cpName = labelIdx >= 0 ? extractNameFromLabel(row[labelIdx], cp) : cp

      edges.push({ counterparty: cp, counterpartyName: cpName, direction: dir, totalAmount: amount, count })
    }

    return edges.length > 0 ? edges : null
  } catch {
    return null
  }
}

function parseCsvLine(line: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuotes = !inQuotes
    } else if (ch === ',' && !inQuotes) {
      result.push(current.trim())
      current = ''
    } else {
      current += ch
    }
  }
  result.push(current.trim())
  return result
}

function extractNameFromLabel(label: string, fallback: string): string {
  // Labels like "Sent To (3 transactions)" — not useful as name
  if (!label || label.includes('transactions)') || label.includes('Sent To') || label.includes('Received From')) {
    return fallback
  }
  return label
}

function aggregateFromRows(rows: any[], subjectAccount: string): AggEdge[] {
  const map = new Map<string, AggEdge>()

  for (const row of rows) {
    const amount = Math.abs(parseFloat(row.amount) || 0)
    if (amount === 0) continue

    const direction = String(row.direction || '').toUpperCase()
    const cpAcct = String(
      row.counterparty_account_normalized || row.counterparty_account || row.from_account || row.to_account || ''
    ).trim()
    const cpName = String(
      row.counterparty_name_normalized || row.counterparty_name || row.counterparty_name_raw || cpAcct || ''
    ).trim()

    let cp: string
    let displayName: string
    let dir: 'IN' | 'OUT'

    if (direction === 'IN') {
      cp = cpAcct || 'UNKNOWN_IN'
      displayName = cpName || cp
      dir = 'IN'
    } else if (direction === 'OUT') {
      cp = cpAcct || 'UNKNOWN_OUT'
      displayName = cpName || cp
      dir = 'OUT'
    } else {
      continue
    }

    if (!cp || cp === subjectAccount) continue

    const key = `${cp}::${dir}`
    const existing = map.get(key)
    if (existing) {
      existing.totalAmount += amount
      existing.count += 1
      if (!existing.counterpartyName || existing.counterpartyName === cp) {
        existing.counterpartyName = displayName
      }
    } else {
      map.set(key, { counterparty: cp, counterpartyName: displayName, direction: dir, totalAmount: amount, count: 1 })
    }
  }

  return Array.from(map.values())
}

function buildElements(account: string, bankKey: string, flows: AggEdge[]) {
  const cpSet = new Map<string, string>()
  for (const f of flows) {
    const existing = cpSet.get(f.counterparty)
    if (!existing || existing === f.counterparty) {
      cpSet.set(f.counterparty, f.counterpartyName)
    }
  }
  const counterparties = Array.from(cpSet.entries())

  const nodes: cytoscape.ElementDefinition[] = [
    {
      data: {
        id: account,
        label: account,
        nodeType: 'subject',
        bankKey: bankKey,
        logoUrl: `/api/bank-logos/${bankKey}.svg`,
      },
    },
  ]

  counterparties.forEach(([cpAcct, cpName]) => {
    nodes.push({
      data: {
        id: cpAcct,
        label: cpName.length > 20 ? cpName.slice(0, 20) + '\u2026' : cpName,
        fullLabel: cpName,
        nodeType: 'counterparty',
      },
    })
  })

  const edges: cytoscape.ElementDefinition[] = []
  for (const f of flows) {
    const edgeId = `${f.counterparty}::${f.direction}`
    if (f.direction === 'IN') {
      edges.push({
        data: {
          id: edgeId,
          source: f.counterparty,
          target: account,
          label: formatAmount(f.totalAmount),
          flowDirection: 'IN',
          amount: f.totalAmount,
          count: f.count,
        },
      })
    } else {
      edges.push({
        data: {
          id: edgeId,
          source: account,
          target: f.counterparty,
          label: formatAmount(f.totalAmount),
          flowDirection: 'OUT',
          amount: f.totalAmount,
          count: f.count,
        },
      })
    }
  }

  return [...nodes, ...edges]
}

const cytoscapeStyle: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node[nodeType="subject"]',
    style: {
      'background-color': '#f59e0b',
      'border-color': '#d97706',
      'border-width': 3,
      width: 60,
      height: 60,
      label: 'data(label)',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'font-size': '11px',
      'font-family': 'TH Sarabun New, Tahoma, sans-serif',
      color: '#f1f5f9',
      'text-margin-y': 8,
      'text-outline-color': '#0f172a',
      'text-outline-width': 2,
      'background-image': 'data(logoUrl)',
      'background-fit': 'contain',
      'background-clip': 'node',
    },
  },
  {
    selector: 'node[nodeType="counterparty"]',
    style: {
      'background-color': '#334155',
      'border-color': '#64748b',
      'border-width': 2,
      width: 32,
      height: 32,
      label: 'data(label)',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'font-size': '10px',
      'font-family': 'TH Sarabun New, Tahoma, sans-serif',
      color: '#94a3b8',
      'text-margin-y': 6,
      'text-outline-color': '#0f172a',
      'text-outline-width': 1,
      'text-wrap': 'wrap',
      'text-max-width': '90px',
    },
  },
  {
    selector: 'node:active',
    style: { 'overlay-opacity': 0.15, 'overlay-color': '#38bdf8' },
  },
  {
    selector: 'node:grabbed',
    style: { 'border-color': '#38bdf8', 'border-width': 3 },
  },
  {
    selector: 'edge[flowDirection="IN"]',
    style: {
      'line-color': '#16a34a',
      'target-arrow-color': '#16a34a',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 1,
      'curve-style': 'bezier',
      width: 1.5,
      label: 'data(label)',
      'font-size': '8px',
      'font-family': 'TH Sarabun New, Tahoma, sans-serif',
      color: '#22c55e',
      'text-outline-color': '#0f172a',
      'text-outline-width': 2,
      'text-rotation': 'autorotate',
      'text-margin-y': -10,
    },
  },
  {
    selector: 'edge[flowDirection="OUT"]',
    style: {
      'line-color': '#dc2626',
      'target-arrow-color': '#dc2626',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 1,
      'curve-style': 'bezier',
      width: 1.5,
      label: 'data(label)',
      'font-size': '8px',
      'font-family': 'TH Sarabun New, Tahoma, sans-serif',
      color: '#f87171',
      'text-outline-color': '#0f172a',
      'text-outline-width': 2,
      'text-rotation': 'autorotate',
      'text-margin-y': -10,
    },
  },
]

export function AccountFlowGraph({ account, bankKey, rows }: FlowGraphProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [flows, setFlows] = useState<AggEdge[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCp, setSelectedCp] = useState<string | null>(null)

  // Load data: prefer aggregated CSV, fallback to raw rows
  useEffect(() => {
    let cancelled = false
    setLoading(true)

    fetchAggregatedEdges(account).then(aggEdges => {
      if (cancelled) return
      if (aggEdges && aggEdges.length > 0) {
        setFlows(aggEdges)
      } else {
        setFlows(aggregateFromRows(rows, account))
      }
      setLoading(false)
    })

    return () => { cancelled = true }
  }, [account, rows])

  const elements = useMemo(() => buildElements(account, bankKey, flows), [account, bankKey, flows])

  const totalIn = useMemo(() => flows.filter(f => f.direction === 'IN').reduce((s, f) => s + f.totalAmount, 0), [flows])
  const totalOut = useMemo(() => flows.filter(f => f.direction === 'OUT').reduce((s, f) => s + f.totalAmount, 0), [flows])
  const cpCount = useMemo(() => new Set(flows.map(f => f.counterparty)).size, [flows])

  const applyLayout = useCallback((mode: 'circle' | 'spread' | 'compact') => {
    const cy = cyRef.current
    if (!cy) return

    const center = cy.getElementById(account)
    // Unlock all nodes for layout
    cy.nodes().unlock()

    let layoutOpts: any
    if (mode === 'circle') {
      // Equal radius circle around center
      const others = cy.nodes().filter(n => n.id() !== account)
      const count = others.length
      const radius = Math.min(400, 150 + count * 2)
      const cx = 400
      const cyy = 400
      center.position({ x: cx, y: cyy })
      others.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / count - Math.PI / 2
        node.position({
          x: cx + radius * Math.cos(angle),
          y: cyy + radius * Math.sin(angle),
        })
      })
      center.lock()
      cy.fit(undefined, 30)
      return
    } else if (mode === 'spread') {
      // Force-directed with strong repulsion — no overlap
      layoutOpts = {
        name: 'cose',
        animate: false,
        nodeOverlap: 80,
        idealEdgeLength: () => 120,
        nodeRepulsion: () => 800000,
        gravity: 0.15,
        numIter: 500,
        padding: 40,
        nodeDimensionsIncludeLabels: true,
      }
    } else {
      // Compact — allow overlap, tight packing
      layoutOpts = {
        name: 'cose',
        animate: false,
        nodeOverlap: 4,
        idealEdgeLength: () => 50,
        nodeRepulsion: () => 50000,
        gravity: 0.8,
        numIter: 300,
        padding: 20,
        nodeDimensionsIncludeLabels: false,
      }
    }

    const layout = cy.layout(layoutOpts)
    layout.on('layoutstop', () => {
      center.lock()
      cy.fit(undefined, 30)
    })
    layout.run()
  }, [account])

  useEffect(() => {
    if (!containerRef.current || elements.length === 0) return

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: cytoscapeStyle,
      layout: {
        name: 'cose',
        animate: false,
        nodeOverlap: 80,
        idealEdgeLength: () => 120,
        nodeRepulsion: () => 800000,
        gravity: 0.15,
        numIter: 500,
        padding: 40,
        nodeDimensionsIncludeLabels: true,
      } as any,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      minZoom: 0.1,
      maxZoom: 5,
    })

    cy.on('layoutstop', () => {
      cy.fit(undefined, 30)
    })

    // Click node to show transaction detail
    cy.on('tap', 'node[nodeType="counterparty"]', (evt) => {
      const nodeId = evt.target.id()
      setSelectedCp(prev => prev === nodeId ? null : nodeId)
    })
    // Click background to deselect
    cy.on('tap', (evt) => {
      if (evt.target === cy) setSelectedCp(null)
    })

    cyRef.current = cy

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [elements, account])

  // Transactions for selected counterparty
  const selectedDetail = useMemo(() => {
    if (!selectedCp) return null
    const cpFlows = flows.filter(f => f.counterparty === selectedCp)
    const cpName = cpFlows[0]?.counterpartyName || selectedCp
    const inFlow = cpFlows.find(f => f.direction === 'IN')
    const outFlow = cpFlows.find(f => f.direction === 'OUT')

    // Filter raw transaction rows for this counterparty
    const txns = rows.filter(r => {
      const cp = String(r.counterparty_account_normalized || r.counterparty_account || r.from_account || r.to_account || '').trim()
      return cp === selectedCp
    }).slice(0, 50) // Limit to 50 rows for display

    return { cpName, inFlow, outFlow, txns, totalTxns: cpFlows.reduce((s, f) => s + f.count, 0) }
  }, [selectedCp, flows, rows])

  if (loading || flows.length === 0) return null

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <CardTitle className="text-text">{t('results.flowGraph.title')}</CardTitle>
        <div className="flex items-center gap-3">
          <div className="flex gap-1 rounded-lg border border-border bg-surface2 p-0.5">
            <button
              onClick={() => applyLayout('circle')}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium text-muted hover:text-text hover:bg-accent/10 transition-colors cursor-pointer"
              title={t('results.flowGraph.layoutCircle')}
            >
              <Circle size={12} />
              {t('results.flowGraph.layoutCircle')}
            </button>
            <button
              onClick={() => applyLayout('spread')}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium text-muted hover:text-text hover:bg-accent/10 transition-colors cursor-pointer"
              title={t('results.flowGraph.layoutSpread')}
            >
              <Maximize2 size={12} />
              {t('results.flowGraph.layoutSpread')}
            </button>
            <button
              onClick={() => applyLayout('compact')}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium text-muted hover:text-text hover:bg-accent/10 transition-colors cursor-pointer"
              title={t('results.flowGraph.layoutCompact')}
            >
              <Minimize2 size={12} />
              {t('results.flowGraph.layoutCompact')}
            </button>
          </div>
          <div className="flex gap-3 text-xs">
            <span className="text-green-400">
              {t('results.flowGraph.totalIn')}: <strong>{formatAmount(totalIn)}</strong>
            </span>
            <span className="text-red-400">
              {t('results.flowGraph.totalOut')}: <strong>{formatAmount(totalOut)}</strong>
            </span>
            <span className="text-muted">
              {cpCount} {t('results.flowGraph.counterparties')}
            </span>
          </div>
        </div>
      </div>
      <div
        ref={containerRef}
        className="w-full rounded-lg border border-border bg-[#0f172a]"
        style={{ height: Math.min(900, 450 + cpCount * 2) }}
      />

      {selectedDetail && (
        <div className="mt-3 rounded-lg border border-accent/30 bg-surface2 p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h4 className="text-sm font-bold text-text">{selectedDetail.cpName}</h4>
              <p className="text-xs text-muted">
                {t('results.flowGraph.detailAccount')}: {selectedCp} &middot; {selectedDetail.totalTxns} {t('results.flowGraph.detailTxns')}
              </p>
            </div>
            <button onClick={() => setSelectedCp(null)} className="text-muted hover:text-text cursor-pointer p-1">
              <X size={16} />
            </button>
          </div>

          <div className="flex gap-4 mb-3 text-xs">
            {selectedDetail.inFlow && (
              <div className="rounded-md bg-green-900/30 border border-green-800/40 px-3 py-1.5">
                <span className="text-green-400 font-semibold">{t('results.flowGraph.totalIn')}</span>
                <span className="ml-2 text-green-300 font-bold">{formatAmount(selectedDetail.inFlow.totalAmount)}</span>
                <span className="ml-1 text-green-400/60">({selectedDetail.inFlow.count} {t('results.flowGraph.detailTxns')})</span>
              </div>
            )}
            {selectedDetail.outFlow && (
              <div className="rounded-md bg-red-900/30 border border-red-800/40 px-3 py-1.5">
                <span className="text-red-400 font-semibold">{t('results.flowGraph.totalOut')}</span>
                <span className="ml-2 text-red-300 font-bold">{formatAmount(selectedDetail.outFlow.totalAmount)}</span>
                <span className="ml-1 text-red-400/60">({selectedDetail.outFlow.count} {t('results.flowGraph.detailTxns')})</span>
              </div>
            )}
          </div>

          {selectedDetail.txns.length > 0 && (
            <div className="overflow-x-auto max-h-64 overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-surface2">
                  <tr className="border-b border-border text-muted text-left">
                    <th className="px-2 py-1.5 font-semibold">{t('results.flowGraph.colDate')}</th>
                    <th className="px-2 py-1.5 font-semibold">{t('results.flowGraph.colAmount')}</th>
                    <th className="px-2 py-1.5 font-semibold">{t('results.flowGraph.colDir')}</th>
                    <th className="px-2 py-1.5 font-semibold">{t('results.flowGraph.colType')}</th>
                    <th className="px-2 py-1.5 font-semibold">{t('results.flowGraph.colDesc')}</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedDetail.txns.map((txn, i) => {
                    const dir = String(txn.direction || '').toUpperCase()
                    const isIn = dir === 'IN'
                    return (
                      <tr key={i} className="border-b border-border/50 hover:bg-accent/5">
                        <td className="px-2 py-1 text-text2">{String(txn.transaction_datetime || txn.posted_date || txn.date || '—').slice(0, 10)}</td>
                        <td className={`px-2 py-1 font-mono font-medium ${isIn ? 'text-green-400' : 'text-red-400'}`}>
                          {isIn ? '+' : '-'}{formatAmount(Math.abs(parseFloat(txn.amount) || 0))}
                        </td>
                        <td className="px-2 py-1">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${isIn ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'}`}>
                            {dir}
                          </span>
                        </td>
                        <td className="px-2 py-1 text-muted">{String(txn.transaction_type || '—')}</td>
                        <td className="px-2 py-1 text-text2 max-w-[200px] truncate">{String(txn.description_normalized || txn.description_raw || txn.description || '—')}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {selectedDetail.txns.length >= 50 && (
                <p className="text-xs text-muted mt-2 px-2">{t('results.flowGraph.detailLimited')}</p>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
