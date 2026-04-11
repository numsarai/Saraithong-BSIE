import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import cytoscape from 'cytoscape'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Expand, RotateCcw, Download, Filter, Maximize2, Pin, Star,
  Circle, Minimize2, Maximize, GitBranch, Sun, Tag, 
  MousePointer, Eye, EyeOff, Paintbrush,
} from 'lucide-react'
import { getAccountFlows } from '@/api'

interface LinkChartProps {
  initialAccount?: string
  onNodeDoubleClick?: (account: string) => void
}

type LayoutMode = 'circle' | 'spread' | 'compact' | 'hierarchy' | 'peacock'

function formatAmount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toFixed(0)
}

function computeConditionalSize(flowTotal: number): number {
  return Math.max(25, Math.min(70, 25 + Math.log10(Math.max(flowTotal, 1)) * 8))
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
  {
    selector: 'node:selected',
    style: {
      'border-color': '#38bdf8',
      'border-width': 3,
      'overlay-opacity': 0.1,
      'overlay-color': '#38bdf8',
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

const FOCUS_HISTORY_MAX = 10
const DEFAULT_EXPANDED_SIZE = 50
const DEFAULT_LEAF_SIZE = 32

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

  // --- New feature state ---
  const [conditionalFormatting, setConditionalFormatting] = useState(false)
  const [edgeLabelsVisible, setEdgeLabelsVisible] = useState(true)
  const [selectMode, setSelectMode] = useState(false)
  const [selectedCount, setSelectedCount] = useState(0)
  const removedElementsRef = useRef<cytoscape.CollectionReturnValue | null>(null)

  // Apply conditional formatting (node size by flow total, border by alerts)
  const applyConditionalFormatting = useCallback((enabled: boolean) => {
    const cy = cyRef.current
    if (!cy) return

    cy.nodes().forEach((node) => {
      if (enabled) {
        const flowTotal = node.data('flowTotal') as number | undefined
        const hasAlerts = node.data('hasAlerts') as boolean | undefined
        const size = computeConditionalSize(flowTotal ?? 0)
        node.style('width', size)
        node.style('height', size)
        if (hasAlerts) {
          node.style('border-color', '#ef4444')
          node.style('border-width', 3)
        }
      } else {
        const isExpanded = node.data('nodeType') === 'expanded'
        const defaultSize = isExpanded ? DEFAULT_EXPANDED_SIZE : DEFAULT_LEAF_SIZE
        node.style('width', defaultSize)
        node.style('height', defaultSize)
        // Restore default border (let stylesheet handle it)
        node.removeStyle('border-color')
        node.removeStyle('border-width')
      }
    })
  }, [])

  // Toggle conditional formatting
  const handleToggleConditionalFormatting = useCallback(() => {
    const next = !conditionalFormatting
    setConditionalFormatting(next)
    applyConditionalFormatting(next)
  }, [conditionalFormatting, applyConditionalFormatting])

  // Toggle edge labels
  const handleToggleEdgeLabels = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const next = !edgeLabelsVisible
    setEdgeLabelsVisible(next)
    cy.edges().style('label', next ? 'data(label)' : '')
  }, [edgeLabelsVisible])

  // Toggle select mode
  const handleToggleSelectMode = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const next = !selectMode
    setSelectMode(next)
    if (!next) {
      // Exiting select mode: deselect all
      cy.nodes().unselect()
      setSelectedCount(0)
    }
    cy.boxSelectionEnabled(next)
  }, [selectMode])

  // Hide selected nodes
  const handleHideSelected = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const selected = cy.nodes(':selected')
    if (selected.length === 0) return
    // Collect nodes and their connected edges
    const toRemove = selected.union(selected.connectedEdges())
    const removed = cy.remove(toRemove)
    // Accumulate removed elements
    if (removedElementsRef.current) {
      removedElementsRef.current = removedElementsRef.current.union(removed)
    } else {
      removedElementsRef.current = removed
    }
    setSelectedCount(0)
    setNodeCount(cy.nodes().length)
    setEdgeCount(cy.edges().length)
  }, [])

  // Show all hidden nodes
  const handleShowAll = useCallback(() => {
    const cy = cyRef.current
    if (!cy || !removedElementsRef.current) return
    removedElementsRef.current.restore()
    removedElementsRef.current = null
    setNodeCount(cy.nodes().length)
    setEdgeCount(cy.edges().length)
    // Re-apply conditional formatting if active
    if (conditionalFormatting) {
      applyConditionalFormatting(true)
    }
    // Re-apply edge label visibility
    if (!edgeLabelsVisible) {
      cy.edges().style('label', '')
    }
  }, [conditionalFormatting, applyConditionalFormatting, edgeLabelsVisible])

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
      case 'hierarchy':
        cy.layout({
          name: 'breadthfirst',
          directed: true,
          spacingFactor: 1.2,
          animate: true,
          animationDuration: 400,
          padding: 40,
          nodeDimensionsIncludeLabels: true,
        } as any).run()
        break
      case 'peacock':
        cy.layout({
          name: 'concentric',
          concentric: (node: cytoscape.NodeSingular) => node.degree(false),
          levelWidth: () => 2,
          animate: true,
          animationDuration: 400,
          padding: 40,
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

    // Single click -> select node (or multi-select in select mode)
    cy.on('tap', 'node', async (evt) => {
      const nodeId = evt.target.id()
      setSelectedNode(nodeId)
      // Update selected count for select mode
      setTimeout(() => {
        setSelectedCount(cy.nodes(':selected').length)
      }, 0)
    })

    // Double click -> entity profile
    cy.on('dbltap', 'node', (evt) => {
      const nodeId = evt.target.id()
      if (onNodeDoubleClick) onNodeDoubleClick(nodeId)
    })

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null)
        setTimeout(() => {
          setSelectedCount(cy.nodes(':selected').length)
        }, 0)
      }
    })

    // Track selection changes for select mode
    cy.on('select unselect', 'node', () => {
      setSelectedCount(cy.nodes(':selected').length)
    })

    cyRef.current = cy
    return () => { cy.destroy(); cyRef.current = null }
  }, [onNodeDoubleClick])

  // Update box selection when selectMode changes
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.boxSelectionEnabled(selectMode)
    cy.userPanningEnabled(!selectMode)
  }, [selectMode])

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
          data: { id: account, label: account, nodeType: 'expanded', flowTotal: 0 },
        })
      } else {
        cy.getElementById(account).data('nodeType', 'expanded')
      }

      // Compute total flow for the center node
      const inboundTotal = (data.inbound || []).reduce((sum: number, f: any) => sum + (f.total || 0), 0)
      const outboundTotal = (data.outbound || []).reduce((sum: number, f: any) => sum + (f.total || 0), 0)
      const centerFlowTotal = inboundTotal + outboundTotal
      cy.getElementById(account).data('flowTotal', centerFlowTotal)

      // Add inbound sources
      for (const flow of (data.inbound || [])) {
        if (flow.total < minAmount) continue
        if (!cy.getElementById(flow.account).length) {
          const lbl = flow.name?.length > 18 ? flow.name.slice(0, 18) + '\u2026' : (flow.name || flow.account)
          newNodes.push({
            data: {
              id: flow.account, label: lbl, fullLabel: flow.name, nodeType: 'leaf',
              flowTotal: flow.total || 0,
              hasAlerts: flow.alerts != null && flow.alerts > 0,
            },
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
            data: {
              id: flow.account, label: lbl, fullLabel: flow.name, nodeType: 'leaf',
              flowTotal: flow.total || 0,
              hasAlerts: flow.alerts != null && flow.alerts > 0,
            },
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

      // Apply conditional formatting to newly added nodes if enabled
      if (conditionalFormatting) {
        applyConditionalFormatting(true)
      }

      // Apply edge label visibility to new edges
      if (!edgeLabelsVisible) {
        cy.edges().style('label', '')
      }

      setExpandedNodes(prev => new Set([...prev, account]))
      addToFocusHistory(account)
      setNodeCount(cy.nodes().length)
      setEdgeCount(cy.edges().length)
    } finally {
      setLoading(false)
    }
  }, [expandedNodes, minAmount, addToFocusHistory, conditionalFormatting, applyConditionalFormatting, edgeLabelsVisible])

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
      removedElementsRef.current = null
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
      removedElementsRef.current = null
      setSelectedCount(0)
      setSelectMode(false)
      setConditionalFormatting(false)
      setEdgeLabelsVisible(true)
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
          {selectMode && selectedCount > 0 && (
            <span className="text-sky-400">{selectedCount} selected</span>
          )}
          {loading && <span className="text-accent animate-pulse">loading...</span>}
        </div>
      </div>

      {/* Toolbar Row 1: Search, actions, filter */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
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

      {/* Toolbar Row 2: Layouts, display toggles, grouping */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
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
          <Button
            variant={activeLayout === 'hierarchy' ? 'outline' : 'ghost'}
            onClick={() => applyLayout('hierarchy')}
            disabled={nodeCount === 0}
            title="Hierarchy layout (top-down tree)"
          >
            <GitBranch size={14} />Hierarchy
          </Button>
          <Button
            variant={activeLayout === 'peacock' ? 'outline' : 'ghost'}
            onClick={() => applyLayout('peacock')}
            disabled={nodeCount === 0}
            title="Peacock layout (high-degree nodes at center)"
          >
            <Sun size={14} />Peacock
          </Button>
        </div>

        <div className="border-l border-border h-6 mx-1" />

        {/* Display toggles */}
        <Button
          variant={edgeLabelsVisible ? 'outline' : 'ghost'}
          onClick={handleToggleEdgeLabels}
          disabled={nodeCount === 0}
          title={edgeLabelsVisible ? 'Hide edge labels' : 'Show edge labels'}
        >
          {edgeLabelsVisible
            ? <><Tag size={14} />Labels</>
            : <><EyeOff size={14} />Labels</>
          }
        </Button>

        <Button
          variant={conditionalFormatting ? 'outline' : 'ghost'}
          onClick={handleToggleConditionalFormatting}
          disabled={nodeCount === 0}
          title="Toggle conditional formatting (size by flow, red border for alerts)"
        >
          <Paintbrush size={14} />Formatting
        </Button>

        <div className="border-l border-border h-6 mx-1" />

        {/* Node grouping / selection */}
        <Button
          variant={selectMode ? 'outline' : 'ghost'}
          onClick={handleToggleSelectMode}
          disabled={nodeCount === 0}
          title={selectMode ? 'Exit multi-select mode' : 'Enter multi-select mode'}
        >
          <MousePointer size={14} />Select
        </Button>

        {selectMode && (
          <>
            <Button
              variant="ghost"
              onClick={handleHideSelected}
              disabled={selectedCount === 0}
              title="Hide selected nodes"
            >
              <EyeOff size={14} />Hide
            </Button>
            <Button
              variant="ghost"
              onClick={handleShowAll}
              disabled={removedElementsRef.current == null}
              title="Restore all hidden nodes"
            >
              <Eye size={14} />Show All
            </Button>
          </>
        )}
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
