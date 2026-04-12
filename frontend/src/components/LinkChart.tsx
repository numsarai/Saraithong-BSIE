import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import cytoscape from 'cytoscape'
import { Card, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Expand, RotateCcw, Download, Filter, Maximize2, Pin, Star,
  Minimize2, Maximize, GitBranch, Sun, Tag,
  MousePointer, Eye, EyeOff, Paintbrush, Shrink,
  Plus, X, Link2,
} from 'lucide-react'
import { getAccountFlows, getMatchedTransactions } from '@/api'

interface LinkChartProps {
  initialAccount?: string
  onNodeDoubleClick?: (account: string) => void
}

type LayoutMode = 'spread' | 'compact' | 'hierarchy' | 'peacock'

interface NodeInfoData {
  id: string
  label: string
  nodeType: string
  flowTotal: number
  isRoot: boolean
  isPinned: boolean
  isExpanded: boolean
  neighbors: { id: string; label: string; direction: 'IN' | 'OUT'; amount: number; count: number }[]
  totalIn: number
  totalOut: number
  // Position relative to graph container
  x: number
  y: number
}

interface N2NDetail {
  nodeA: string
  nodeB: string
  transactions: any[]
  totalIn: number
  totalOut: number
  count: number
}

function formatAmount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toFixed(0)
}

function formatAmountFull(n: number): string {
  return Math.abs(n).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function computeConditionalSize(flowTotal: number): number {
  return Math.max(25, Math.min(70, 25 + Math.log10(Math.max(flowTotal, 1)) * 8))
}

function getGraphBg(): string {
  return getComputedStyle(document.documentElement).getPropertyValue('--color-graph-bg').trim() || '#0f172a'
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
    style: { 'border-color': '#eab308', 'border-width': 3, 'border-style': 'double' },
  },
  {
    selector: 'node[pinned]',
    style: {
      'border-color': '#facc15', 'border-width': 3, 'border-style': 'solid',
      'background-image': 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23facc15" stroke="%23facc15" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
      'background-width': '14px', 'background-height': '14px',
      'background-position-x': '100%', 'background-position-y': '0%',
      'background-clip': 'none', 'background-image-containment': 'over',
    } as any,
  },
  // N2N highlights
  {
    selector: 'node.n2n-a',
    style: { 'border-color': '#38bdf8', 'border-width': 4, 'overlay-opacity': 0.15, 'overlay-color': '#38bdf8' },
  },
  {
    selector: 'node.n2n-b',
    style: { 'border-color': '#a78bfa', 'border-width': 4, 'overlay-opacity': 0.15, 'overlay-color': '#a78bfa' },
  },
  {
    selector: 'node.n2n-dim',
    style: { opacity: 0.25 },
  },
  {
    selector: 'edge.n2n-highlight',
    style: { 'line-color': '#facc15', 'target-arrow-color': '#facc15', width: 4, 'z-index': 10 },
  },
  {
    selector: 'edge.n2n-dim',
    style: { opacity: 0.15 },
  },
  {
    selector: 'node:selected',
    style: { 'border-color': '#38bdf8', 'border-width': 3, 'overlay-opacity': 0.1, 'overlay-color': '#38bdf8' },
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
  const [rootAccounts, setRootAccounts] = useState<Set<string>>(new Set())
  const [nodeCount, setNodeCount] = useState(0)
  const [edgeCount, setEdgeCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [searchAccount, setSearchAccount] = useState(initialAccount || '')
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [minAmount, setMinAmount] = useState(0)
  const [minTxnCount, setMinTxnCount] = useState(0)
  const [pinnedNodes, setPinnedNodes] = useState<Set<string>>(new Set())
  const [focusHistory, setFocusHistory] = useState<string[]>([])
  const [activeLayout, setActiveLayout] = useState<LayoutMode>('spread')
  const [isFullscreen, setIsFullscreen] = useState(false)

  const [conditionalFormatting, setConditionalFormatting] = useState(false)
  const [edgeLabelsVisible, setEdgeLabelsVisible] = useState(true)
  const [selectMode, setSelectMode] = useState(false)
  const [selectedCount, setSelectedCount] = useState(0)
  const removedElementsRef = useRef<cytoscape.CollectionReturnValue | null>(null)

  // Node info card state
  const [nodeInfo, setNodeInfo] = useState<NodeInfoData | null>(null)

  // N2N mode state
  const [n2nMode, setN2nMode] = useState(false)
  const [n2nNodeA, setN2nNodeA] = useState<string | null>(null)
  const [n2nNodeB, setN2nNodeB] = useState<string | null>(null)
  const [n2nDetail, setN2nDetail] = useState<N2NDetail | null>(null)
  const [n2nLoading, setN2nLoading] = useState(false)

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
        if (hasAlerts) { node.style('border-color', '#ef4444'); node.style('border-width', 3) }
      } else {
        const isExpanded = node.data('nodeType') === 'expanded'
        node.style('width', isExpanded ? DEFAULT_EXPANDED_SIZE : DEFAULT_LEAF_SIZE)
        node.style('height', isExpanded ? DEFAULT_EXPANDED_SIZE : DEFAULT_LEAF_SIZE)
        node.removeStyle('border-color')
        node.removeStyle('border-width')
      }
    })
  }, [])

  const handleToggleConditionalFormatting = useCallback(() => {
    const next = !conditionalFormatting
    setConditionalFormatting(next)
    applyConditionalFormatting(next)
  }, [conditionalFormatting, applyConditionalFormatting])

  const handleToggleEdgeLabels = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const next = !edgeLabelsVisible
    setEdgeLabelsVisible(next)
    cy.edges().style('label', next ? 'data(label)' : '')
  }, [edgeLabelsVisible])

  const handleToggleSelectMode = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const next = !selectMode
    setSelectMode(next)
    if (!next) { cy.nodes().unselect(); setSelectedCount(0) }
    cy.boxSelectionEnabled(next)
    cy.userPanningEnabled(!next)
  }, [selectMode])

  const handleHideSelected = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    const selected = cy.nodes(':selected')
    if (selected.length === 0) return
    const removed = cy.remove(selected.union(selected.connectedEdges()))
    removedElementsRef.current = removedElementsRef.current
      ? removedElementsRef.current.union(removed) : removed
    setSelectedCount(0)
    setNodeCount(cy.nodes().length)
    setEdgeCount(cy.edges().length)
  }, [])

  const handleShowAll = useCallback(() => {
    const cy = cyRef.current
    if (!cy || !removedElementsRef.current) return
    removedElementsRef.current.restore()
    removedElementsRef.current = null
    setNodeCount(cy.nodes().length)
    setEdgeCount(cy.edges().length)
    if (conditionalFormatting) applyConditionalFormatting(true)
    if (!edgeLabelsVisible) cy.edges().style('label', '')
  }, [conditionalFormatting, applyConditionalFormatting, edgeLabelsVisible])

  const applyLayout = useCallback((mode: LayoutMode) => {
    const cy = cyRef.current
    if (!cy || cy.nodes().length === 0) return
    setActiveLayout(mode)
    cy.nodes().forEach((node) => { if (!pinnedNodes.has(node.id())) node.unlock() })

    const opts: Record<LayoutMode, any> = {
      spread: { name: 'cose', animate: true, animationDuration: 400, nodeOverlap: 80, idealEdgeLength: () => 140, nodeRepulsion: () => 1200000, gravity: 0.15, numIter: 400, padding: 40, nodeDimensionsIncludeLabels: true },
      compact: { name: 'cose', animate: true, animationDuration: 400, nodeOverlap: 20, idealEdgeLength: () => 50, nodeRepulsion: () => 80000, gravity: 0.8, numIter: 300, padding: 20, nodeDimensionsIncludeLabels: true },
      hierarchy: { name: 'breadthfirst', directed: true, spacingFactor: 1.2, animate: true, animationDuration: 400, padding: 40, nodeDimensionsIncludeLabels: true },
      peacock: { name: 'concentric', concentric: (node: cytoscape.NodeSingular) => node.degree(false), levelWidth: () => 2, animate: true, animationDuration: 400, padding: 40, nodeDimensionsIncludeLabels: true },
    }
    cy.layout(opts[mode]).run()
    setTimeout(() => { cy.nodes().forEach((node) => { if (pinnedNodes.has(node.id())) node.lock() }) }, 500)
  }, [pinnedNodes])

  const togglePin = useCallback((nodeId: string) => {
    const cy = cyRef.current
    if (!cy) return
    setPinnedNodes((prev) => {
      const next = new Set(prev)
      const node = cy.getElementById(nodeId)
      if (next.has(nodeId)) { next.delete(nodeId); node.data('pinned', false); node.unlock() }
      else { next.add(nodeId); node.data('pinned', true); node.lock() }
      return next
    })
  }, [])

  const addToFocusHistory = useCallback((account: string) => {
    setFocusHistory((prev) => [account, ...prev.filter(i => i !== account)].slice(0, FOCUS_HISTORY_MAX))
  }, [])

  const focusOnNode = useCallback((account: string) => {
    const cy = cyRef.current
    if (!cy) return
    const node = cy.getElementById(account)
    if (node.length) {
      cy.animate({ center: { eles: node }, zoom: 1.5 } as any, { duration: 300 })
      setSelectedNode(account)
    }
  }, [])

  // --- Node Info Card Logic ---
  const buildNodeInfo = useCallback((nodeId: string) => {
    const cy = cyRef.current
    if (!cy) return
    const node = cy.getElementById(nodeId)
    if (!node.length) { setNodeInfo(null); return }

    // Get position relative to the container
    const containerRect = containerRef.current?.getBoundingClientRect()
    const renderedPos = node.renderedPosition()
    const x = renderedPos.x
    const y = renderedPos.y

    // Gather connected edges info
    const connEdges = node.connectedEdges()
    const neighbors: NodeInfoData['neighbors'] = []
    let totalIn = 0
    let totalOut = 0

    connEdges.forEach((edge) => {
      const dir = edge.data('flowDirection') as 'IN' | 'OUT'
      const amount = edge.data('amount') as number || 0
      const count = edge.data('count') as number || 0
      const otherId = edge.source().id() === nodeId ? edge.target().id() : edge.source().id()
      const otherLabel = (edge.source().id() === nodeId ? edge.target() : edge.source()).data('label') || otherId

      if (dir === 'IN' && edge.target().id() === nodeId) {
        totalIn += amount
        neighbors.push({ id: otherId, label: otherLabel, direction: 'IN', amount, count })
      } else if (dir === 'OUT' && edge.source().id() === nodeId) {
        totalOut += amount
        neighbors.push({ id: otherId, label: otherLabel, direction: 'OUT', amount, count })
      } else if (dir === 'IN' && edge.source().id() === nodeId) {
        totalOut += amount
        neighbors.push({ id: otherId, label: otherLabel, direction: 'OUT', amount, count })
      } else if (dir === 'OUT' && edge.target().id() === nodeId) {
        totalIn += amount
        neighbors.push({ id: otherId, label: otherLabel, direction: 'IN', amount, count })
      }
    })

    // Sort neighbors by amount descending
    neighbors.sort((a, b) => b.amount - a.amount)

    setNodeInfo({
      id: nodeId,
      label: node.data('fullLabel') || node.data('label') || nodeId,
      nodeType: node.data('nodeType') || 'leaf',
      flowTotal: node.data('flowTotal') || 0,
      isRoot: rootAccounts.has(nodeId),
      isPinned: pinnedNodes.has(nodeId),
      isExpanded: expandedNodes.has(nodeId),
      neighbors: neighbors.slice(0, 8),
      totalIn,
      totalOut,
      x: Math.min(x, (containerRect?.width || 600) - 260),
      y: Math.max(50, Math.min(y, (containerRect?.height || 400) - 200)),
    })
  }, [rootAccounts, pinnedNodes, expandedNodes])

  // --- N2N Mode Logic ---
  const clearN2nHighlights = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().removeClass('n2n-a n2n-b n2n-dim')
    cy.edges().removeClass('n2n-highlight n2n-dim')
  }, [])

  const exitN2nMode = useCallback(() => {
    clearN2nHighlights()
    setN2nMode(false)
    setN2nNodeA(null)
    setN2nNodeB(null)
    setN2nDetail(null)
  }, [clearN2nHighlights])

  const handleN2nSelect = useCallback(async (nodeId: string) => {
    const cy = cyRef.current
    if (!cy) return

    if (!n2nNodeA) {
      // Select Node A
      setN2nNodeA(nodeId)
      setN2nNodeB(null)
      setN2nDetail(null)
      clearN2nHighlights()
      const nodeA = cy.getElementById(nodeId)
      nodeA.addClass('n2n-a')
      // Dim all non-connected nodes
      const connected = nodeA.neighborhood().nodes()
      cy.nodes().forEach((n) => {
        if (n.id() !== nodeId && !connected.contains(n)) n.addClass('n2n-dim')
      })
      cy.edges().forEach((e) => {
        if (e.source().id() !== nodeId && e.target().id() !== nodeId) e.addClass('n2n-dim')
      })
    } else if (!n2nNodeB && nodeId !== n2nNodeA) {
      // Select Node B
      setN2nNodeB(nodeId)
      clearN2nHighlights()
      const nodeA = cy.getElementById(n2nNodeA)
      const nodeB = cy.getElementById(nodeId)
      nodeA.addClass('n2n-a')
      nodeB.addClass('n2n-b')
      // Dim everything except A, B, and their shared edges
      cy.nodes().forEach((n) => {
        if (n.id() !== n2nNodeA && n.id() !== nodeId) n.addClass('n2n-dim')
      })
      cy.edges().forEach((e) => {
        const sId = e.source().id()
        const tId = e.target().id()
        const connects = (sId === n2nNodeA && tId === nodeId) || (sId === nodeId && tId === n2nNodeA)
        if (connects) e.addClass('n2n-highlight')
        else e.addClass('n2n-dim')
      })

      // Fetch pairwise transactions
      setN2nLoading(true)
      try {
        const data = await getMatchedTransactions(n2nNodeA, nodeId)
        const txns = data.transactions || data || []
        let totalIn = 0
        let totalOut = 0
        for (const txn of txns) {
          const amt = Math.abs(parseFloat(txn.amount) || 0)
          const dir = String(txn.direction || '').toUpperCase()
          if (dir === 'IN') totalIn += amt
          else totalOut += amt
        }
        setN2nDetail({
          nodeA: n2nNodeA, nodeB: nodeId,
          transactions: txns, totalIn, totalOut, count: txns.length,
        })
      } catch {
        setN2nDetail({ nodeA: n2nNodeA, nodeB: nodeId, transactions: [], totalIn: 0, totalOut: 0, count: 0 })
      } finally {
        setN2nLoading(false)
      }
    } else {
      // Reset and start over with new Node A
      clearN2nHighlights()
      setN2nNodeA(nodeId)
      setN2nNodeB(null)
      setN2nDetail(null)
      const nodeA = cy.getElementById(nodeId)
      nodeA.addClass('n2n-a')
      const connected = nodeA.neighborhood().nodes()
      cy.nodes().forEach((n) => {
        if (n.id() !== nodeId && !connected.contains(n)) n.addClass('n2n-dim')
      })
      cy.edges().forEach((e) => {
        if (e.source().id() !== nodeId && e.target().id() !== nodeId) e.addClass('n2n-dim')
      })
    }
  }, [n2nNodeA, n2nNodeB, clearN2nHighlights])

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

    cy.on('tap', 'node', (evt) => {
      const nodeId = evt.target.id()
      setSelectedNode(nodeId)
      setTimeout(() => setSelectedCount(cy.nodes(':selected').length), 0)
      // Show info card (buildNodeInfo is called via effect since it depends on state)
    })

    cy.on('dbltap', 'node', (evt) => {
      if (onNodeDoubleClick) onNodeDoubleClick(evt.target.id())
    })

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null)
        setNodeInfo(null)
        setTimeout(() => setSelectedCount(cy.nodes(':selected').length), 0)
      }
    })

    cy.on('select unselect', 'node', () => {
      setSelectedCount(cy.nodes(':selected').length)
    })

    cyRef.current = cy
    return () => { cy.destroy(); cyRef.current = null }
  }, [onNodeDoubleClick])

  // Handle N2N node selection via tap
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    if (!n2nMode) return

    const handler = (evt: cytoscape.EventObject) => {
      if (evt.target !== cy) handleN2nSelect(evt.target.id())
    }
    cy.on('tap', 'node', handler)
    return () => { cy.removeListener('tap', 'node', handler) }
  }, [n2nMode, handleN2nSelect])

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

      if (!cy.getElementById(account).length) {
        newNodes.push({ data: { id: account, label: account, nodeType: 'expanded', flowTotal: 0 } })
      } else {
        cy.getElementById(account).data('nodeType', 'expanded')
      }

      const inboundTotal = (data.inbound || []).reduce((s: number, f: any) => s + (f.total || 0), 0)
      const outboundTotal = (data.outbound || []).reduce((s: number, f: any) => s + (f.total || 0), 0)
      cy.getElementById(account).data('flowTotal', inboundTotal + outboundTotal)

      for (const flow of (data.inbound || [])) {
        if (flow.total < minAmount || flow.count < minTxnCount) continue
        if (!cy.getElementById(flow.account).length) {
          const lbl = flow.name?.length > 18 ? flow.name.slice(0, 18) + '\u2026' : (flow.name || flow.account)
          newNodes.push({ data: { id: flow.account, label: lbl, fullLabel: flow.name, nodeType: 'leaf', flowTotal: flow.total || 0, hasAlerts: flow.alerts != null && flow.alerts > 0 } })
        }
        const edgeId = `${flow.account}::${account}::IN`
        if (!cy.getElementById(edgeId).length) {
          newEdges.push({ data: { id: edgeId, source: flow.account, target: account, label: formatAmount(flow.total), flowDirection: 'IN', amount: flow.total, count: flow.count, edgeWidth: Math.max(1, Math.log10(Math.max(flow.total, 1)) * 0.8) } })
        }
      }

      for (const flow of (data.outbound || [])) {
        if (flow.total < minAmount || flow.count < minTxnCount) continue
        if (!cy.getElementById(flow.account).length) {
          const lbl = flow.name?.length > 18 ? flow.name.slice(0, 18) + '\u2026' : (flow.name || flow.account)
          newNodes.push({ data: { id: flow.account, label: lbl, fullLabel: flow.name, nodeType: 'leaf', flowTotal: flow.total || 0, hasAlerts: flow.alerts != null && flow.alerts > 0 } })
        }
        const edgeId = `${account}::${flow.account}::OUT`
        if (!cy.getElementById(edgeId).length) {
          newEdges.push({ data: { id: edgeId, source: account, target: flow.account, label: formatAmount(flow.total), flowDirection: 'OUT', amount: flow.total, count: flow.count, edgeWidth: Math.max(1, Math.log10(Math.max(flow.total, 1)) * 0.8) } })
        }
      }

      if (newNodes.length || newEdges.length) {
        cy.add([...newNodes, ...newEdges])
        cy.layout({ name: 'cose', animate: false, nodeOverlap: 60, idealEdgeLength: () => 100, nodeRepulsion: () => 600000, gravity: 0.2, numIter: 300, padding: 30, nodeDimensionsIncludeLabels: true } as any).run()
      }

      if (conditionalFormatting) applyConditionalFormatting(true)
      if (!edgeLabelsVisible) cy.edges().style('label', '')

      setExpandedNodes(prev => new Set([...prev, account]))
      addToFocusHistory(account)
      setNodeCount(cy.nodes().length)
      setEdgeCount(cy.edges().length)
    } finally {
      setLoading(false)
    }
  }, [expandedNodes, minAmount, minTxnCount, addToFocusHistory, conditionalFormatting, applyConditionalFormatting, edgeLabelsVisible])

  // Auto-expand selected node if not already expanded (only when NOT in N2N mode)
  useEffect(() => {
    if (n2nMode) return
    if (selectedNode && !expandedNodes.has(selectedNode)) expandNode(selectedNode)
  }, [selectedNode, n2nMode, expandNode, expandedNodes])

  // Build node info card when selectedNode changes
  useEffect(() => {
    if (selectedNode && !n2nMode) {
      // Small delay to let expand finish if needed
      const timer = setTimeout(() => buildNodeInfo(selectedNode), 100)
      return () => clearTimeout(timer)
    } else {
      setNodeInfo(null)
    }
  }, [selectedNode, n2nMode, buildNodeInfo])

  // --- Multi-Account handlers ---
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
      exitN2nMode()
    }
    setRootAccounts(new Set([acct]))
    setSelectedNode(acct)
  }

  const handleAddAccount = () => {
    const acct = searchAccount.replace(/\D/g, '')
    if (!acct) return
    setRootAccounts(prev => new Set([...prev, acct]))
    if (!expandedNodes.has(acct)) {
      expandNode(acct)
    }
    setSearchAccount('')
  }

  const handleRemoveAccount = (acct: string) => {
    const cy = cyRef.current
    if (!cy) return
    // Remove the root node and its leaf-only neighbors
    const node = cy.getElementById(acct)
    if (!node.length) return
    const neighbors = node.neighborhood().nodes()
    const toRemove = cy.collection()
    toRemove.merge(node)
    // Remove leaves that are only connected to this root
    neighbors.forEach((n) => {
      if (n.data('nodeType') === 'leaf' && n.degree(false) <= 1) {
        toRemove.merge(n)
      }
    })
    toRemove.merge(toRemove.connectedEdges())
    cy.remove(toRemove)
    setRootAccounts(prev => { const next = new Set(prev); next.delete(acct); return next })
    setExpandedNodes(prev => { const next = new Set(prev); next.delete(acct); return next })
    setNodeCount(cy.nodes().length)
    setEdgeCount(cy.edges().length)
  }

  const handleReset = () => {
    const cy = cyRef.current
    if (cy) cy.elements().remove()
    setExpandedNodes(new Set())
    setRootAccounts(new Set())
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
    exitN2nMode()
  }

  const handleFit = () => { cyRef.current?.fit(undefined, 30) }

  const handleExportPng = () => {
    const cy = cyRef.current
    if (!cy) return
    const png = cy.png({ scale: 2, bg: getGraphBg() })
    const a = document.createElement('a')
    a.href = png
    a.download = 'link_chart.png'
    a.click()
  }

  const graphHeight = isFullscreen ? '100%' : (nodeCount > 0 ? Math.min(700, 400 + nodeCount * 2) : 300)
  const wrapperClassName = isFullscreen ? 'fixed inset-0 z-50 bg-bg flex flex-col p-4' : 'p-4'

  return (
    <Card className={wrapperClassName}>
      {/* Stats bar */}
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <CardTitle className="text-text">{t('linkChart.title')}</CardTitle>
        <div className="flex items-center gap-2 text-xs text-muted">
          <span>{nodeCount} nodes</span>
          <span>{edgeCount} edges</span>
          {rootAccounts.size > 0 && <span className="text-amber-400">{rootAccounts.size} root</span>}
          {pinnedNodes.size > 0 && <span className="text-yellow-400">{pinnedNodes.size} pinned</span>}
          {n2nMode && <span className="text-violet-400">N2N</span>}
          {loading && <span className="text-accent animate-pulse">loading...</span>}
        </div>
      </div>

      {/* Root account chips */}
      {rootAccounts.size > 0 && (
        <div className="flex items-center gap-1.5 mb-2 flex-wrap">
          <span className="text-[10px] text-muted uppercase tracking-wide">{t('linkChart.rootAccounts')}:</span>
          {Array.from(rootAccounts).map((acct) => (
            <span key={acct} className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-0.5 text-xs font-mono text-amber-400">
              {acct}
              <button onClick={() => handleRemoveAccount(acct)} className="hover:text-danger cursor-pointer"><X size={10} /></button>
            </span>
          ))}
        </div>
      )}

      {/* Graph container with floating toolbar */}
      <div className={`relative ${isFullscreen ? 'flex-1' : ''}`}>
        {nodeCount === 0 && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <span className="text-muted text-sm">{t('linkChart.hint')}</span>
          </div>
        )}

        <div
          ref={containerRef}
          className="w-full rounded-lg border border-border"
          style={{ height: graphHeight, background: 'var(--color-graph-bg)' }}
        />

        {/* Floating toolbar */}
        <div className="absolute top-2 left-2 right-2 flex flex-wrap items-center gap-1.5 backdrop-blur-sm rounded-lg px-2.5 py-1.5 border shadow-sm">
          {/* Search + Add */}
          <input
            value={searchAccount}
            onChange={e => setSearchAccount(e.target.value.replace(/\D/g, ''))}
            placeholder={t('linkChart.startAccount')}
            className="bg-surface2 border border-border rounded-lg px-2.5 py-1 text-[11px] text-text focus:border-sky-500 outline-none w-28"
            onKeyDown={e => { if (e.key === 'Enter') { nodeCount === 0 ? handleStart() : handleAddAccount() } }}
          />
          {nodeCount === 0 ? (
            <Button variant="success" size="sm" onClick={handleStart} disabled={!searchAccount || loading}>
              <Expand size={13} />{t('linkChart.explore')}
            </Button>
          ) : (
            <Button variant="success" size="sm" onClick={handleAddAccount} disabled={!searchAccount || loading}>
              <Plus size={13} />{t('linkChart.addAccount')}
            </Button>
          )}

          <div className="border-l border-border h-5 mx-0.5" />

          {/* Layouts */}
          {(['spread', 'compact', 'hierarchy', 'peacock'] as LayoutMode[]).map((mode) => {
            const icons = { spread: Maximize, compact: Minimize2, hierarchy: GitBranch, peacock: Sun }
            const Icon = icons[mode]
            return (
              <Button key={mode} variant={activeLayout === mode ? 'outline' : 'ghost'} size="sm"
                onClick={() => applyLayout(mode)} disabled={nodeCount === 0}>
                <Icon size={13} />{mode.charAt(0).toUpperCase() + mode.slice(1)}
              </Button>
            )
          })}

          <div className="border-l border-border h-5 mx-0.5" />

          {/* Filters */}
          <div className="flex items-center gap-1">
            <Filter size={11} className="text-muted" />
            <span className="text-[10px] text-muted">{t('linkChart.minAmount')}:</span>
            <input type="number" value={minAmount || ''} placeholder="0"
              onChange={e => setMinAmount(Number(e.target.value) || 0)}
              className="bg-surface2 border border-border rounded px-1.5 py-0.5 text-[11px] text-text w-16 outline-none" />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[10px] text-muted">{t('linkChart.minTxnCount')}:</span>
            <input type="number" value={minTxnCount || ''} placeholder="0"
              onChange={e => setMinTxnCount(Number(e.target.value) || 0)}
              className="bg-surface2 border border-border rounded px-1.5 py-0.5 text-[11px] text-text w-16 outline-none" />
          </div>

          <div className="border-l border-border h-5 mx-0.5" />

          {/* Toggles */}
          <Button variant={edgeLabelsVisible ? 'outline' : 'ghost'} size="sm" onClick={handleToggleEdgeLabels} disabled={nodeCount === 0}>
            {edgeLabelsVisible ? <Tag size={13} /> : <EyeOff size={13} />}
          </Button>
          <Button variant={conditionalFormatting ? 'outline' : 'ghost'} size="sm" onClick={handleToggleConditionalFormatting} disabled={nodeCount === 0}>
            <Paintbrush size={13} />
          </Button>

          <div className="border-l border-border h-5 mx-0.5" />

          {/* N2N Mode */}
          <Button variant={n2nMode ? 'outline' : 'ghost'} size="sm"
            onClick={() => { if (n2nMode) exitN2nMode(); else { setN2nMode(true); setSelectMode(false) } }}
            disabled={nodeCount === 0}
            title={t('linkChart.n2n')}
          >
            <Link2 size={13} />N2N
          </Button>

          {/* Pin */}
          <Button variant={selectedNode && pinnedNodes.has(selectedNode) ? 'outline' : 'ghost'} size="sm"
            onClick={() => selectedNode && togglePin(selectedNode)} disabled={!selectedNode}>
            {selectedNode && pinnedNodes.has(selectedNode) ? <Star size={13} className="text-yellow-400" /> : <Pin size={13} />}
          </Button>

          {/* Select mode */}
          <Button variant={selectMode ? 'outline' : 'ghost'} size="sm" onClick={handleToggleSelectMode} disabled={nodeCount === 0 || n2nMode}>
            <MousePointer size={13} />
          </Button>
          {selectMode && (
            <>
              <Button variant="ghost" size="sm" onClick={handleHideSelected} disabled={selectedCount === 0}><EyeOff size={13} /></Button>
              <Button variant="ghost" size="sm" onClick={handleShowAll} disabled={removedElementsRef.current == null}><Eye size={13} /></Button>
            </>
          )}

          <div className="border-l border-border h-5 mx-0.5" />

          {/* Actions */}
          <Button variant="ghost" size="sm" onClick={handleFit}><Maximize2 size={13} /></Button>
          <Button variant="ghost" size="sm" onClick={handleReset}><RotateCcw size={13} /></Button>
          <Button variant="ghost" size="sm" onClick={handleExportPng}><Download size={13} /></Button>
          <Button variant="ghost" size="sm" onClick={() => setIsFullscreen(f => !f)}>
            {isFullscreen ? <Shrink size={13} /> : <Expand size={13} />}
          </Button>
        </div>

        {/* N2N Detail Panel — floating bottom-right */}
        {n2nMode && n2nNodeA && (
          <div className="absolute bottom-3 right-3 w-80 max-h-72 overflow-auto bg-surface/90 backdrop-blur-sm rounded-lg border border-border p-3 text-xs">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-text">
                {n2nNodeB ? `${n2nNodeA} \u2194 ${n2nNodeB}` : t('linkChart.n2nSelectB')}
              </span>
              <button onClick={exitN2nMode} className="text-muted hover:text-text cursor-pointer"><X size={14} /></button>
            </div>

            {n2nLoading && <div className="text-accent animate-pulse py-2">{t('linkChart.loading')}...</div>}

            {n2nDetail && (
              <>
                <div className="flex gap-3 mb-2">
                  <div className="rounded bg-green-900/40 border border-green-800/40 px-2 py-1">
                    <span className="text-green-400">{t('linkChart.n2nIn')}: </span>
                    <strong className="text-green-300">{formatAmountFull(n2nDetail.totalIn)}</strong>
                  </div>
                  <div className="rounded bg-red-900/40 border border-red-800/40 px-2 py-1">
                    <span className="text-red-400">{t('linkChart.n2nOut')}: </span>
                    <strong className="text-red-300">{formatAmountFull(n2nDetail.totalOut)}</strong>
                  </div>
                </div>
                <div className="text-muted mb-2">{n2nDetail.count} {t('linkChart.n2nTxns')}</div>

                {n2nDetail.transactions.length > 0 && (
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="text-muted border-b border-border text-left">
                        <th className="py-1 pr-2">{t('linkChart.n2nDate')}</th>
                        <th className="py-1 pr-2">{t('linkChart.n2nAmount')}</th>
                        <th className="py-1">{t('linkChart.n2nDir')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {n2nDetail.transactions.slice(0, 30).map((txn, i) => {
                        const dir = String(txn.direction || '').toUpperCase()
                        const isIn = dir === 'IN'
                        return (
                          <tr key={i} className="border-b border-border/50 hover:bg-surface2">
                            <td className="py-0.5 pr-2 text-text2">{String(txn.transaction_datetime || txn.posted_date || txn.date || '').slice(0, 10)}</td>
                            <td className={`py-0.5 pr-2 font-mono ${isIn ? 'text-green-400' : 'text-red-400'}`}>
                              {isIn ? '+' : '-'}{formatAmountFull(Math.abs(parseFloat(txn.amount) || 0))}
                            </td>
                            <td className="py-0.5">
                              <span className={`px-1 rounded text-[9px] font-bold ${isIn ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>{dir}</span>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
                {n2nDetail.transactions.length > 30 && (
                  <div className="text-muted mt-1">{t('linkChart.n2nLimited')}</div>
                )}
              </>
            )}

            {!n2nNodeB && !n2nLoading && (
              <div className="text-muted py-2">
                <span className="inline-block w-3 h-3 rounded-full bg-sky-400/30 border border-sky-400 mr-1" />
                {t('linkChart.n2nHintA')}
              </div>
            )}
          </div>
        )}

        {/* Node Info Card — floating near clicked node */}
        {nodeInfo && !n2nMode && (
          <div
            className="absolute z-20 w-60 bg-surface/95 backdrop-blur-sm rounded-lg border border-border shadow-xl text-xs pointer-events-auto"
            style={{ left: nodeInfo.x + 20, top: nodeInfo.y - 20 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-border/50">
              <div className="flex-1 min-w-0">
                <div className="font-bold text-slate-100 truncate">{nodeInfo.label}</div>
                <div className="text-[10px] text-muted font-mono">{nodeInfo.id}</div>
              </div>
              <div className="flex items-center gap-1 ml-2 shrink-0">
                {nodeInfo.isRoot && <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-[9px] font-bold">{t('linkChart.nodeInfoRoot')}</span>}
                {nodeInfo.isExpanded && <span className="px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 text-[9px] font-bold">{t('linkChart.expanded')}</span>}
                {nodeInfo.isPinned && <Star size={10} className="text-yellow-400" />}
              </div>
              <button onClick={() => setNodeInfo(null)} className="ml-1.5 text-muted hover:text-text2 cursor-pointer"><X size={12} /></button>
            </div>

            {/* Flow summary */}
            <div className="flex gap-2 px-3 py-2">
              <div className="flex-1 rounded bg-green-900/30 border border-green-800/30 px-2 py-1 text-center">
                <div className="text-[9px] text-green-500">{t('linkChart.n2nIn')}</div>
                <div className="font-bold text-green-400">{formatAmount(nodeInfo.totalIn)}</div>
              </div>
              <div className="flex-1 rounded bg-red-900/30 border border-red-800/30 px-2 py-1 text-center">
                <div className="text-[9px] text-red-500">{t('linkChart.n2nOut')}</div>
                <div className="font-bold text-red-400">{formatAmount(nodeInfo.totalOut)}</div>
              </div>
            </div>

            {/* Neighbors list */}
            {nodeInfo.neighbors.length > 0 && (
              <div className="px-3 pb-2">
                <div className="text-[9px] text-muted uppercase tracking-wide mb-1">{t('linkChart.nodeInfoConnections')} ({nodeInfo.neighbors.length}{nodeInfo.neighbors.length >= 8 ? '+' : ''})</div>
                <div className="max-h-32 overflow-y-auto space-y-0.5">
                  {nodeInfo.neighbors.map((nb, i) => (
                    <div key={i}
                      className="flex items-center gap-1.5 rounded px-1.5 py-0.5 hover:bg-surface2 cursor-pointer"
                      onClick={() => { setSelectedNode(nb.id); setNodeInfo(null) }}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${nb.direction === 'IN' ? 'bg-green-400' : 'bg-red-400'}`} />
                      <span className="text-text2 truncate flex-1">{nb.label}</span>
                      <span className={`font-mono text-[10px] ${nb.direction === 'IN' ? 'text-green-400' : 'text-red-400'}`}>
                        {nb.direction === 'IN' ? '+' : '-'}{formatAmount(nb.amount)}
                      </span>
                      <span className="text-slate-600 text-[9px]">{nb.count}x</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Focus history */}
      {focusHistory.length > 0 && (
        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          <span className="text-[10px] text-muted uppercase tracking-wide">History:</span>
          {focusHistory.map((acct) => (
            <button key={acct} onClick={() => focusOnNode(acct)}
              className={['rounded-full border px-2.5 py-0.5 text-xs font-mono transition-all cursor-pointer',
                acct === selectedNode ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-surface2 text-muted hover:border-accent/40 hover:text-text',
              ].join(' ')}>
              {acct}
              {pinnedNodes.has(acct) && <Star size={10} className="inline ml-1 text-yellow-400" />}
            </button>
          ))}
        </div>
      )}

      {/* Selected node info */}
      {selectedNode && !n2nMode && (
        <div className="mt-2 text-xs text-muted flex items-center gap-3">
          <span>{t('linkChart.selected')}: <strong className="text-text font-mono">{selectedNode}</strong></span>
          {expandedNodes.has(selectedNode)
            ? <span className="text-green-400">{t('linkChart.expanded')}</span>
            : <span className="text-accent">{t('linkChart.clickToExpand')}</span>}
          {pinnedNodes.has(selectedNode) && <span className="text-yellow-400 flex items-center gap-1"><Star size={10} /> Pinned</span>}
        </div>
      )}
    </Card>
  )
}
