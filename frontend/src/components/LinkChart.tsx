import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import cytoscape from 'cytoscape'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Expand, RotateCcw, Download, Filter, Maximize2, Pin, Star, Circle, Minimize2, Maximize } from 'lucide-react'
import { getAccountFlows } from '@/api'

interface LinkChartProps {
  initialAccount?: string
  onNodeDoubleClick?: (account: string) => void
}

type LayoutMode = 'circle' | 'spread' | 'compact'

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
  {
    selector: 'node[pinned]',
    style: {
      'border-color': '#facc15',
      'border-width': 3,
      'border-style': 'solid',
      'background-image': 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23facc15" stroke="%23facc15" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
      'background-width': '14px',
      'background-height': '14px',
      'background-position-x': '100%',
      'background-position-y': '0%',
      'background-clip': 'none',
      'background-image-containment': 'over',
    } as any,
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

const FOCUS_HISTORY_MAX = 10

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
  const [pinnedNodes, setPinnedNodes] = useState<Set<string>>(new Set())
  const [focusHistory, setFocusHistory] = useState<string[]>([])
  const [activeLayout, setActiveLayout] = useState<LayoutMode>('spread')

  // Apply a layout mode to all existing nodes
  const applyLayout = useCallback((mode: LayoutMode) => {
    const cy = cyRef.current
    if (!cy || cy.nodes().length === 0) return

    setActiveLayout(mode)

    // Unlock non-pinned nodes before layout
    cy.nodes().forEach((node) => {
      if (!pinnedNodes.has(node.id())) {
        node.unlock()
      }
    })

    switch (mode) {
      case 'circle':
        cy.layout({
          name: 'circle',
          animate: true,
          animationDuration: 400,
          padding: 40,
          nodeDimensionsIncludeLabels: true,
        } as any).run()
        break
      case 'spread':
        cy.layout({
          name: 'cose',
          animate: true,
          animationDuration: 400,
          nodeOverlap: 80,
          idealEdgeLength: () => 140,
          nodeRepulsion: () => 1200000,
          gravity: 0.15,
          numIter: 400,
          padding: 40,
          nodeDimensionsIncludeLabels: true,
        } as any).run()
        break
      case 'compact':
        cy.layout({
          name: 'cose',
          animate: true,
          animationDuration: 400,
          nodeOverlap: 20,
          idealEdgeLength: () => 50,
          nodeRepulsion: () => 80000,
          gravity: 0.8,
          numIter: 300,
          padding: 20,
          nodeDimensionsIncludeLabels: true,
        } as any).run()
        break
    }

    // Re-lock pinned nodes after layout settles
    setTimeout(() => {
      cy.nodes().forEach((node) => {
        if (pinnedNodes.has(node.id())) {
          node.lock()
        }
      })
    }, 500)
  }, [pinnedNodes])

  // Toggle pin on a node
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

  // Add to focus history
  const addToFocusHistory = useCallback((account: string) => {
    setFocusHistory((prev) => {
      const filtered = prev.filter((item) => item !== account)
      const next = [account, ...filtered]
      return next.slice(0, FOCUS_HISTORY_MAX)
    })
  }, [])

  // Focus on a node from history
  const focusOnNode = useCallback((account: string) => {
    const cy = cyRef.current
    if (!cy) return
    const node = cy.getElementById(account)
    if (node.length) {
      cy.animate({
        center: { eles: node },
        zoom: 1.5,
      } as any, { duration: 300 })
      setSelectedNode(account)
    }
  }, [])

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

    // Single click -> select + expand
    cy.on('tap', 'node', async (evt) => {
      const nodeId = evt.target.id()
      setSelectedNode(nodeId)
    })

    // Double click -> entity profile
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

  // Expand a node -- load its neighbors
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
      addToFocusHistory(account)
      setNodeCount(cy.nodes().length)
      setEdgeCount(cy.edges().length)
    } finally {
      setLoading(false)
    }
  }, [expandedNodes, minAmount, addToFocusHistory])

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
      setPinnedNodes(new Set())
      setFocusHistory([])
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
      setPinnedNodes(new Set())
      setFocusHistory([])
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
          {pinnedNodes.size > 0 && <span className="text-yellow-400">{pinnedNodes.size} pinned</span>}
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
        <div className="border-l border-border h-6 mx-1" />

        {/* Layout switcher */}
        <div className="flex items-center gap-1">
          <Button
            variant={activeLayout === 'circle' ? 'outline' : 'ghost'}
            onClick={() => applyLayout('circle')}
            disabled={nodeCount === 0}
            title="Circle layout"
          >
            <Circle size={14} />Circle
          </Button>
          <Button
            variant={activeLayout === 'spread' ? 'outline' : 'ghost'}
            onClick={() => applyLayout('spread')}
            disabled={nodeCount === 0}
            title="Spread layout (high repulsion)"
          >
            <Maximize size={14} />Spread
          </Button>
          <Button
            variant={activeLayout === 'compact' ? 'outline' : 'ghost'}
            onClick={() => applyLayout('compact')}
            disabled={nodeCount === 0}
            title="Compact layout (tight)"
          >
            <Minimize2 size={14} />Compact
          </Button>
        </div>
        <div className="border-l border-border h-6 mx-1" />

        {/* Pin button */}
        <Button
          variant={selectedNode && pinnedNodes.has(selectedNode) ? 'outline' : 'ghost'}
          onClick={() => selectedNode && togglePin(selectedNode)}
          disabled={!selectedNode}
          title={selectedNode && pinnedNodes.has(selectedNode) ? 'Unpin node' : 'Pin node in place'}
        >
          {selectedNode && pinnedNodes.has(selectedNode)
            ? <><Star size={14} className="text-yellow-400" />Unpin</>
            : <><Pin size={14} />Pin</>
          }
        </Button>
      </div>

      {/* Focus history chips */}
      {focusHistory.length > 0 && (
        <div className="flex items-center gap-1.5 mb-3 flex-wrap">
          <span className="text-[10px] text-muted uppercase tracking-wide">History:</span>
          {focusHistory.map((account) => (
            <button
              key={account}
              onClick={() => focusOnNode(account)}
              className={[
                'rounded-full border px-2.5 py-0.5 text-xs font-mono transition-all',
                account === selectedNode
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border bg-surface2 text-muted hover:border-accent/40 hover:text-text',
              ].join(' ')}
            >
              {account}
              {pinnedNodes.has(account) && <Star size={10} className="inline ml-1 text-yellow-400" />}
            </button>
          ))}
        </div>
      )}

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
          {pinnedNodes.has(selectedNode) && (
            <span className="text-yellow-400 flex items-center gap-1">
              <Star size={10} /> Pinned
            </span>
          )}
        </div>
      )}
    </Card>
  )
}
