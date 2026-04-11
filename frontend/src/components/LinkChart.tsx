import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import cytoscape from 'cytoscape'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Expand, RotateCcw, Download, Filter, Maximize2 } from 'lucide-react'
import { getAccountFlows } from '@/api'

interface LinkChartProps {
  initialAccount?: string
  onNodeDoubleClick?: (account: string) => void
}

function formatAmount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toFixed(0)
}

const chartStyle: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node[nodeType="expanded"]',
    style: {
      'background-color': '#f59e0b',
      'border-color': '#d97706',
      'border-width': 3,
      width: 50,
      height: 50,
      label: 'data(label)',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'font-size': '10px',
      'font-family': 'TH Sarabun New, Tahoma, sans-serif',
      color: '#f1f5f9',
      'text-margin-y': 6,
      'text-outline-color': '#0f172a',
      'text-outline-width': 2,
    },
  },
  {
    selector: 'node[nodeType="leaf"]',
    style: {
      'background-color': '#334155',
      'border-color': '#64748b',
      'border-width': 2,
      width: 32,
      height: 32,
      label: 'data(label)',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'font-size': '9px',
      'font-family': 'TH Sarabun New, Tahoma, sans-serif',
      color: '#94a3b8',
      'text-margin-y': 5,
      'text-outline-color': '#0f172a',
      'text-outline-width': 1,
    },
  },
  {
    selector: 'node[hasAnnotation]',
    style: {
      'border-color': '#eab308',
      'border-width': 3,
      'border-style': 'double',
    },
  },
  { selector: 'node:active', style: { 'overlay-opacity': 0.15, 'overlay-color': '#38bdf8' } },
  { selector: 'node:grabbed', style: { 'border-color': '#38bdf8', 'border-width': 3 } },
  {
    selector: 'edge[flowDirection="IN"]',
    style: {
      'line-color': '#16a34a', 'target-arrow-color': '#16a34a', 'target-arrow-shape': 'triangle',
      'curve-style': 'bezier', width: 'data(edgeWidth)', label: 'data(label)',
      'font-size': '8px', 'font-family': 'TH Sarabun New, Tahoma, sans-serif',
      color: '#22c55e', 'text-outline-color': '#0f172a', 'text-outline-width': 2,
      'text-rotation': 'autorotate', 'text-margin-y': -8, 'arrow-scale': 0.8,
    },
  },
  {
    selector: 'edge[flowDirection="OUT"]',
    style: {
      'line-color': '#dc2626', 'target-arrow-color': '#dc2626', 'target-arrow-shape': 'triangle',
      'curve-style': 'bezier', width: 'data(edgeWidth)', label: 'data(label)',
      'font-size': '8px', 'font-family': 'TH Sarabun New, Tahoma, sans-serif',
      color: '#f87171', 'text-outline-color': '#0f172a', 'text-outline-width': 2,
      'text-rotation': 'autorotate', 'text-margin-y': -8, 'arrow-scale': 0.8,
    },
  },
]

export function LinkChart({ initialAccount, onNodeDoubleClick }: LinkChartProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [nodeCount, setNodeCount] = useState(0)
  const [edgeCount, setEdgeCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [searchAccount, setSearchAccount] = useState(initialAccount || '')
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [minAmount, setMinAmount] = useState(0)

  // Initialize cytoscape
  useEffect(() => {
    if (!containerRef.current) return
    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: chartStyle,
      layout: { name: 'preset' },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      minZoom: 0.05,
      maxZoom: 5,
    })

    // Single click → select + expand
    cy.on('tap', 'node', async (evt) => {
      const nodeId = evt.target.id()
      setSelectedNode(nodeId)
    })

    // Double click → entity profile
    cy.on('dbltap', 'node', (evt) => {
      const nodeId = evt.target.id()
      if (onNodeDoubleClick) onNodeDoubleClick(nodeId)
    })

    cy.on('tap', (evt) => {
      if (evt.target === cy) setSelectedNode(null)
    })

    cyRef.current = cy
    return () => { cy.destroy(); cyRef.current = null }
  }, [onNodeDoubleClick])

  // Expand a node — load its neighbors
  const expandNode = useCallback(async (account: string) => {
    const cy = cyRef.current
    if (!cy || expandedNodes.has(account)) return

    setLoading(true)
    try {
      const data = await getAccountFlows(account)
      const newNodes: cytoscape.ElementDefinition[] = []
      const newEdges: cytoscape.ElementDefinition[] = []

      // Ensure center node exists
      if (!cy.getElementById(account).length) {
        newNodes.push({
          data: { id: account, label: account, nodeType: 'expanded' },
        })
      } else {
        cy.getElementById(account).data('nodeType', 'expanded')
      }

      // Add inbound sources
      for (const flow of (data.inbound || [])) {
        if (flow.total < minAmount) continue
        if (!cy.getElementById(flow.account).length) {
          const lbl = flow.name?.length > 18 ? flow.name.slice(0, 18) + '\u2026' : (flow.name || flow.account)
          newNodes.push({
            data: { id: flow.account, label: lbl, fullLabel: flow.name, nodeType: 'leaf' },
          })
        }
        const edgeId = `${flow.account}::${account}::IN`
        if (!cy.getElementById(edgeId).length) {
          newEdges.push({
            data: {
              id: edgeId, source: flow.account, target: account,
              label: formatAmount(flow.total), flowDirection: 'IN',
              amount: flow.total, count: flow.count,
              edgeWidth: Math.max(1, Math.log10(Math.max(flow.total, 1)) * 0.8),
            },
          })
        }
      }

      // Add outbound targets
      for (const flow of (data.outbound || [])) {
        if (flow.total < minAmount) continue
        if (!cy.getElementById(flow.account).length) {
          const lbl = flow.name?.length > 18 ? flow.name.slice(0, 18) + '\u2026' : (flow.name || flow.account)
          newNodes.push({
            data: { id: flow.account, label: lbl, fullLabel: flow.name, nodeType: 'leaf' },
          })
        }
        const edgeId = `${account}::${flow.account}::OUT`
        if (!cy.getElementById(edgeId).length) {
          newEdges.push({
            data: {
              id: edgeId, source: account, target: flow.account,
              label: formatAmount(flow.total), flowDirection: 'OUT',
              amount: flow.total, count: flow.count,
              edgeWidth: Math.max(1, Math.log10(Math.max(flow.total, 1)) * 0.8),
            },
          })
        }
      }

      if (newNodes.length || newEdges.length) {
        cy.add([...newNodes, ...newEdges])
        // Run layout only on new elements
        cy.layout({
          name: 'cose',
          animate: false,
          nodeOverlap: 60,
          idealEdgeLength: () => 100,
          nodeRepulsion: () => 600000,
          gravity: 0.2,
          numIter: 300,
          padding: 30,
          nodeDimensionsIncludeLabels: true,
        } as any).run()
      }

      setExpandedNodes(prev => new Set([...prev, account]))
      setNodeCount(cy.nodes().length)
      setEdgeCount(cy.edges().length)
    } finally {
      setLoading(false)
    }
  }, [expandedNodes, minAmount])

  // Start / expand from selected node
  useEffect(() => {
    if (selectedNode && !expandedNodes.has(selectedNode)) {
      expandNode(selectedNode)
    }
  }, [selectedNode])

  // Handle initial account
  const handleStart = () => {
    const acct = searchAccount.replace(/\D/g, '')
    if (!acct) return
    const cy = cyRef.current
    if (cy) {
      cy.elements().remove()
      setExpandedNodes(new Set())
    }
    setSelectedNode(acct)
  }

  const handleReset = () => {
    const cy = cyRef.current
    if (cy) {
      cy.elements().remove()
      setExpandedNodes(new Set())
      setNodeCount(0)
      setEdgeCount(0)
      setSelectedNode(null)
    }
  }

  const handleFit = () => { cyRef.current?.fit(undefined, 30) }

  const handleExportPng = () => {
    const cy = cyRef.current
    if (!cy) return
    const png = cy.png({ scale: 2, bg: '#0f172a' })
    const a = document.createElement('a')
    a.href = png
    a.download = 'link_chart.png'
    a.click()
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <CardTitle className="text-text">{t('linkChart.title')}</CardTitle>
        <div className="flex items-center gap-2 text-xs text-muted">
          <span>{nodeCount} nodes</span>
          <span>{edgeCount} edges</span>
          {loading && <span className="text-accent animate-pulse">loading...</span>}
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <input
          value={searchAccount}
          onChange={e => setSearchAccount(e.target.value.replace(/\D/g, ''))}
          placeholder={t('linkChart.startAccount')}
          className="bg-surface2 border border-border rounded-lg px-3 py-1.5 text-sm text-text focus:border-accent outline-none w-36"
          onKeyDown={e => e.key === 'Enter' && handleStart()}
        />
        <Button variant="success" onClick={handleStart} disabled={!searchAccount || loading}>
          <Expand size={14} />{t('linkChart.explore')}
        </Button>
        <div className="border-l border-border h-6 mx-1" />
        <Button variant="ghost" onClick={handleFit}><Maximize2 size={14} /></Button>
        <Button variant="ghost" onClick={handleReset}><RotateCcw size={14} /></Button>
        <Button variant="ghost" onClick={handleExportPng}><Download size={14} />PNG</Button>
        <div className="border-l border-border h-6 mx-1" />
        <div className="flex items-center gap-1">
          <Filter size={12} className="text-muted" />
          <span className="text-[10px] text-muted">{t('linkChart.minAmount')}:</span>
          <input
            type="number"
            value={minAmount || ''}
            onChange={e => setMinAmount(Number(e.target.value) || 0)}
            placeholder="0"
            className="bg-surface2 border border-border rounded px-2 py-1 text-xs text-text w-20 outline-none"
          />
        </div>
      </div>

      {/* Hint */}
      {nodeCount === 0 && (
        <div className="text-center text-muted text-sm py-8">
          {t('linkChart.hint')}
        </div>
      )}

      {/* Chart container */}
      <div
        ref={containerRef}
        className="w-full rounded-lg border border-border bg-[#0f172a]"
        style={{ height: nodeCount > 0 ? Math.min(700, 400 + nodeCount * 2) : 300 }}
      />

      {/* Selected node info */}
      {selectedNode && (
        <div className="mt-2 text-xs text-muted flex items-center gap-3">
          <span>{t('linkChart.selected')}: <strong className="text-text font-mono">{selectedNode}</strong></span>
          {expandedNodes.has(selectedNode)
            ? <span className="text-green-400">{t('linkChart.expanded')}</span>
            : <span className="text-accent">{t('linkChart.clickToExpand')}</span>
          }
        </div>
      )}
    </Card>
  )
}
