import { useEffect, useRef, useMemo, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import cytoscape from 'cytoscape'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Maximize2, Minimize2, X, Download, Filter, Pin, Star,
  Maximize, GitBranch, Sun, Tag, EyeOff, Eye, Paintbrush,
  MousePointer, Expand, Shrink,
} from 'lucide-react'

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

type LayoutMode = 'spread' | 'compact' | 'hierarchy' | 'peacock'

function formatAmount(n: number): string {
  return Math.abs(n).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatAmountShort(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toFixed(0)
}

function computeConditionalSize(flowTotal: number): number {
  return Math.max(25, Math.min(70, 25 + Math.log10(Math.max(flowTotal, 1)) * 8))
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
        flowTotal: flows.reduce((s, f) => s + f.totalAmount, 0),
      },
    },
  ]

  counterparties.forEach(([cpAcct, cpName]) => {
    const cpFlows = flows.filter(f => f.counterparty === cpAcct)
    const flowTotal = cpFlows.reduce((s, f) => s + f.totalAmount, 0)
    nodes.push({
      data: {
        id: cpAcct,
        label: cpName.length > 20 ? cpName.slice(0, 20) + '\u2026' : cpName,
        fullLabel: cpName,
        nodeType: 'counterparty',
        flowTotal,
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
          label: formatAmountShort(f.totalAmount),
          flowDirection: 'IN',
          amount: f.totalAmount,
          count: f.count,
          edgeWidth: Math.max(1, Math.log10(Math.max(f.totalAmount, 1)) * 0.8),
        },
      })
    } else {
      edges.push({
        data: {
          id: edgeId,
          source: account,
          target: f.counterparty,
          label: formatAmountShort(f.totalAmount),
          flowDirection: 'OUT',
          amount: f.totalAmount,
          count: f.count,
          edgeWidth: Math.max(1, Math.log10(Math.max(f.totalAmount, 1)) * 0.8),
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
    selector: 'node[pinned]',
    style: {
      'border-color': '#facc15',
      'border-width': 3,
      'border-style': 'solid',
    } as any,
  },
  {
    selector: 'node:selected',
    style: {
      'border-color': '#38bdf8',
      'border-width': 3,
      'overlay-opacity': 0.1,
      'overlay-color': '#38bdf8',
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
      'arrow-scale': 0.8,
      'curve-style': 'bezier',
      width: 'data(edgeWidth)',
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
      'arrow-scale': 0.8,
      'curve-style': 'bezier',
      width: 'data(edgeWidth)',
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

const DEFAULT_SUBJECT_SIZE = 60
const DEFAULT_CP_SIZE = 32

export function AccountFlowGraph({ account, bankKey, rows }: FlowGraphProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [flows, setFlows] = useState<AggEdge[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCp, setSelectedCp] = useState<string | null>(null)

  // New feature state
  const [activeLayout, setActiveLayout] = useState<LayoutMode>('spread')
  const [minAmount, setMinAmount] = useState(0)
  const [minTxnCount, setMinTxnCount] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [pinnedNodes, setPinnedNodes] = useState<Set<string>>(new Set())
  const [conditionalFormatting, setConditionalFormatting] = useState(false)
  const [edgeLabelsVisible, setEdgeLabelsVisible] = useState(true)
  const [selectMode, setSelectMode] = useState(false)
  const [selectedCount, setSelectedCount] = useState(0)
  const removedElementsRef = useRef<cytoscape.CollectionReturnValue | null>(null)

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

  // Filter flows by minAmount and minTxnCount
  const filteredFlows = useMemo(() =>
    flows.filter(f => f.totalAmount >= minAmount && f.count >= minTxnCount),
    [flows, minAmount, minTxnCount]
  )

  const elements = useMemo(() => buildElements(account, bankKey, filteredFlows), [account, bankKey, filteredFlows])

  const totalIn = useMemo(() => filteredFlows.filter(f => f.direction === 'IN').reduce((s, f) => s + f.totalAmount, 0), [filteredFlows])
  const totalOut = useMemo(() => filteredFlows.filter(f => f.direction === 'OUT').reduce((s, f) => s + f.totalAmount, 0), [filteredFlows])
  const cpCount = useMemo(() => new Set(filteredFlows.map(f => f.counterparty)).size, [filteredFlows])

  // Apply conditional formatting
  const applyConditionalFormatting = useCallback((enabled: boolean) => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().forEach((node) => {
      if (enabled) {
        const flowTotal = node.data('flowTotal') as number | undefined
        const size = computeConditionalSize(flowTotal ?? 0)
        node.style('width', size)
        node.style('height', size)
      } else {
        const isSubject = node.data('nodeType') === 'subject'
        const defaultSize = isSubject ? DEFAULT_SUBJECT_SIZE : DEFAULT_CP_SIZE
        node.style('width', defaultSize)
        node.style('height', defaultSize)
      }
    })
  }, [])

  const applyLayout = useCallback((mode: LayoutMode) => {
    const cy = cyRef.current
    if (!cy || cy.nodes().length === 0) return

    setActiveLayout(mode)

    // Unlock non-pinned nodes
    cy.nodes().forEach((node) => {
      if (!pinnedNodes.has(node.id())) node.unlock()
    })

    let layoutOpts: any
    switch (mode) {
      case 'spread':
        layoutOpts = {
          name: 'cose', animate: true, animationDuration: 400,
          nodeOverlap: 80, idealEdgeLength: () => 120,
          nodeRepulsion: () => 800000, gravity: 0.15, numIter: 500,
          padding: 40, nodeDimensionsIncludeLabels: true,
        }
        break
      case 'compact':
        layoutOpts = {
          name: 'cose', animate: true, animationDuration: 400,
          nodeOverlap: 20, idealEdgeLength: () => 50,
          nodeRepulsion: () => 50000, gravity: 0.8, numIter: 300,
          padding: 20, nodeDimensionsIncludeLabels: true,
        }
        break
      case 'hierarchy':
        layoutOpts = {
          name: 'breadthfirst', directed: true, spacingFactor: 1.2,
          animate: true, animationDuration: 400, padding: 40,
          nodeDimensionsIncludeLabels: true,
        }
        break
      case 'peacock':
        layoutOpts = {
          name: 'concentric',
          concentric: (node: cytoscape.NodeSingular) => node.degree(false),
          levelWidth: () => 2, animate: true, animationDuration: 400,
          padding: 40, nodeDimensionsIncludeLabels: true,
        }
        break
    }

    cy.layout(layoutOpts).run()

    // Re-lock pinned nodes after layout settles
    setTimeout(() => {
      cy.nodes().forEach((node) => {
        if (pinnedNodes.has(node.id())) node.lock()
      })
    }, 500)
  }, [pinnedNodes])

  // Toggle pin
  const togglePin = useCallback((nodeId: string) => {
    const cy = cyRef.current
    if (!cy) return
    setPinnedNodes((prev) => {
      const next = new Set(prev)
      const node = cy.getElementById(nodeId)
      if (next.has(nodeId)) {
        next.delete(nodeId)
        node.data('pinned', false)
        node.unlock()
      } else {
        next.add(nodeId)
        node.data('pinned', true)
        node.lock()
      }
      return next
    })
  }, [])

  // Toggle edge labels
  const handleToggleEdgeLabels = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const next = !edgeLabelsVisible
    setEdgeLabelsVisible(next)
    cy.edges().style('label', next ? 'data(label)' : '')
  }, [edgeLabelsVisible])

  // Toggle conditional formatting
  const handleToggleConditionalFormatting = useCallback(() => {
    const next = !conditionalFormatting
    setConditionalFormatting(next)
    applyConditionalFormatting(next)
  }, [conditionalFormatting, applyConditionalFormatting])

  // Toggle select mode
  const handleToggleSelectMode = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const next = !selectMode
    setSelectMode(next)
    if (!next) {
      cy.nodes().unselect()
      setSelectedCount(0)
    }
    cy.boxSelectionEnabled(next)
    cy.userPanningEnabled(!next)
  }, [selectMode])

  // Hide selected nodes
  const handleHideSelected = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const selected = cy.nodes(':selected')
    if (selected.length === 0) return
    const toRemove = selected.union(selected.connectedEdges())
    const removed = cy.remove(toRemove)
    if (removedElementsRef.current) {
      removedElementsRef.current = removedElementsRef.current.union(removed)
    } else {
      removedElementsRef.current = removed
    }
    setSelectedCount(0)
  }, [])

  // Show all hidden nodes
  const handleShowAll = useCallback(() => {
    const cy = cyRef.current
    if (!cy || !removedElementsRef.current) return
    removedElementsRef.current.restore()
    removedElementsRef.current = null
    if (conditionalFormatting) applyConditionalFormatting(true)
    if (!edgeLabelsVisible) cy.edges().style('label', '')
  }, [conditionalFormatting, applyConditionalFormatting, edgeLabelsVisible])

  const handleFit = useCallback(() => { cyRef.current?.fit(undefined, 30) }, [])

  const handleExportPng = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const graphBg = getComputedStyle(document.documentElement).getPropertyValue('--color-graph-bg').trim() || '#0f172a'
    const png = cy.png({ scale: 2, bg: graphBg })
    const a = document.createElement('a')
    a.href = png
    a.download = `flow_graph_${account}.png`
    a.click()
  }, [account])

  // Initialize cytoscape
  useEffect(() => {
    if (!containerRef.current || elements.length === 0) return

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: cytoscapeStyle,
      layout: {
        name: 'cose', animate: false,
        nodeOverlap: 80, idealEdgeLength: () => 120,
        nodeRepulsion: () => 800000, gravity: 0.15,
        numIter: 500, padding: 40, nodeDimensionsIncludeLabels: true,
      } as any,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      minZoom: 0.05,
      maxZoom: 5,
    })

    cy.on('layoutstop', () => { cy.fit(undefined, 30) })

    cy.on('tap', 'node[nodeType="counterparty"]', (evt) => {
      const nodeId = evt.target.id()
      setSelectedCp(prev => prev === nodeId ? null : nodeId)
    })
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedCp(null)
        setTimeout(() => setSelectedCount(cy.nodes(':selected').length), 0)
      }
    })
    cy.on('select unselect', 'node', () => {
      setSelectedCount(cy.nodes(':selected').length)
    })

    cyRef.current = cy
    return () => { cy.destroy(); cyRef.current = null }
  }, [elements, account])

  // Transactions for selected counterparty
  const selectedDetail = useMemo(() => {
    if (!selectedCp) return null
    const cpFlows = filteredFlows.filter(f => f.counterparty === selectedCp)
    const cpName = cpFlows[0]?.counterpartyName || selectedCp
    const inFlow = cpFlows.find(f => f.direction === 'IN')
    const outFlow = cpFlows.find(f => f.direction === 'OUT')

    const txns = rows.filter(r => {
      const cp = String(r.counterparty_account_normalized || r.counterparty_account || r.from_account || r.to_account || '').trim()
      return cp === selectedCp
    }).slice(0, 50)

    return { cpName, inFlow, outFlow, txns, totalTxns: cpFlows.reduce((s, f) => s + f.count, 0) }
  }, [selectedCp, filteredFlows, rows])

  if (loading || flows.length === 0) return null

  const graphHeight = isFullscreen ? '100%' : Math.min(900, 450 + cpCount * 2)

  const wrapperClassName = isFullscreen
    ? 'fixed inset-0 z-50 bg-surface flex flex-col p-4'
    : ''

  return (
    <Card className={isFullscreen ? wrapperClassName : 'p-4'}>
      {/* Stats bar */}
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <CardTitle className="text-text">{t('results.flowGraph.title')}</CardTitle>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-green-400">
            {t('results.flowGraph.totalIn')}: <strong>{formatAmount(totalIn)}</strong>
          </span>
          <span className="text-red-400">
            {t('results.flowGraph.totalOut')}: <strong>{formatAmount(totalOut)}</strong>
          </span>
          <span className="text-muted">
            {cpCount} {t('results.flowGraph.counterparties')}
          </span>
          {pinnedNodes.size > 0 && <span className="text-yellow-400">{pinnedNodes.size} pinned</span>}
          {selectMode && selectedCount > 0 && <span className="text-sky-400">{selectedCount} selected</span>}
        </div>
      </div>

      {/* Graph container with floating toolbar */}
      <div className={`relative ${isFullscreen ? 'flex-1' : ''}`}>
        <div
          ref={containerRef}
          className="w-full rounded-lg border border-border bg-[var(--color-graph-bg)]"
          style={{ height: graphHeight }}
        />

        {/* Floating toolbar inside canvas */}
        <div className="absolute top-2 left-2 right-2 flex flex-wrap items-center gap-1.5 bg-slate-900/85 backdrop-blur-sm rounded-lg px-2.5 py-1.5 border border-slate-700/50">
          {/* Layouts */}
          <Button
            variant={activeLayout === 'spread' ? 'outline' : 'ghost'} size="sm"
            onClick={() => applyLayout('spread')} title={t('results.flowGraph.layoutSpread')}
          >
            <Maximize size={13} />{t('results.flowGraph.layoutSpread')}
          </Button>
          <Button
            variant={activeLayout === 'compact' ? 'outline' : 'ghost'} size="sm"
            onClick={() => applyLayout('compact')} title={t('results.flowGraph.layoutCompact')}
          >
            <Minimize2 size={13} />{t('results.flowGraph.layoutCompact')}
          </Button>
          <Button
            variant={activeLayout === 'hierarchy' ? 'outline' : 'ghost'} size="sm"
            onClick={() => applyLayout('hierarchy')} title={t('results.flowGraph.layoutHierarchy')}
          >
            <GitBranch size={13} />{t('results.flowGraph.layoutHierarchy')}
          </Button>
          <Button
            variant={activeLayout === 'peacock' ? 'outline' : 'ghost'} size="sm"
            onClick={() => applyLayout('peacock')} title={t('results.flowGraph.layoutPeacock')}
          >
            <Sun size={13} />{t('results.flowGraph.layoutPeacock')}
          </Button>

          <div className="border-l border-slate-600 h-5 mx-0.5" />

          {/* Filters */}
          <div className="flex items-center gap-1">
            <Filter size={11} className="text-slate-400" />
            <span className="text-[10px] text-slate-400">{t('results.flowGraph.minAmount')}:</span>
            <input
              type="number" value={minAmount || ''} placeholder="0"
              onChange={e => setMinAmount(Number(e.target.value) || 0)}
              className="bg-slate-800 border border-slate-600 rounded px-1.5 py-0.5 text-[11px] text-slate-200 w-16 outline-none"
            />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[10px] text-slate-400">{t('results.flowGraph.minTxnCount')}:</span>
            <input
              type="number" value={minTxnCount || ''} placeholder="0"
              onChange={e => setMinTxnCount(Number(e.target.value) || 0)}
              className="bg-slate-800 border border-slate-600 rounded px-1.5 py-0.5 text-[11px] text-slate-200 w-16 outline-none"
            />
          </div>

          <div className="border-l border-slate-600 h-5 mx-0.5" />

          {/* Display toggles */}
          <Button variant={edgeLabelsVisible ? 'outline' : 'ghost'} size="sm" onClick={handleToggleEdgeLabels}>
            {edgeLabelsVisible ? <Tag size={13} /> : <EyeOff size={13} />}
          </Button>
          <Button variant={conditionalFormatting ? 'outline' : 'ghost'} size="sm" onClick={handleToggleConditionalFormatting}>
            <Paintbrush size={13} />
          </Button>

          <div className="border-l border-slate-600 h-5 mx-0.5" />

          {/* Pin */}
          <Button
            variant={selectedCp && pinnedNodes.has(selectedCp) ? 'outline' : 'ghost'} size="sm"
            onClick={() => selectedCp && togglePin(selectedCp)} disabled={!selectedCp}
          >
            {selectedCp && pinnedNodes.has(selectedCp)
              ? <Star size={13} className="text-yellow-400" />
              : <Pin size={13} />
            }
          </Button>

          {/* Select mode */}
          <Button variant={selectMode ? 'outline' : 'ghost'} size="sm" onClick={handleToggleSelectMode}>
            <MousePointer size={13} />
          </Button>
          {selectMode && (
            <>
              <Button variant="ghost" size="sm" onClick={handleHideSelected} disabled={selectedCount === 0}>
                <EyeOff size={13} />
              </Button>
              <Button variant="ghost" size="sm" onClick={handleShowAll} disabled={removedElementsRef.current == null}>
                <Eye size={13} />
              </Button>
            </>
          )}

          <div className="border-l border-slate-600 h-5 mx-0.5" />

          {/* Actions */}
          <Button variant="ghost" size="sm" onClick={handleFit}><Maximize2 size={13} /></Button>
          <Button variant="ghost" size="sm" onClick={handleExportPng}><Download size={13} /></Button>
          <Button variant="ghost" size="sm" onClick={() => setIsFullscreen(f => !f)}>
            {isFullscreen ? <Shrink size={13} /> : <Expand size={13} />}
          </Button>
        </div>
      </div>

      {/* Selected counterparty detail */}
      {selectedDetail && !isFullscreen && (
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
