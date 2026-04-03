import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getGraphFindings, getGraphNeighborhood, getGraphNodes } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardTitle } from '@/components/ui/card'

type GraphFilters = Record<string, string | number | undefined>

function shortLabel(value: string) {
  if (!value) return 'Unknown'
  return value.length > 24 ? `${value.slice(0, 24)}…` : value
}

function nodeTone(nodeType: string, suspicious: boolean, center: boolean) {
  if (center) return { fill: '#f59e0b', stroke: '#fbbf24', text: '#111827' }
  if (suspicious) return { fill: '#ef4444', stroke: '#f87171', text: '#ffffff' }
  if (nodeType === 'Account') return { fill: '#2563eb', stroke: '#60a5fa', text: '#ffffff' }
  if (nodeType === 'Bank') return { fill: '#7c3aed', stroke: '#a78bfa', text: '#ffffff' }
  if (nodeType === 'Entity') return { fill: '#0f766e', stroke: '#5eead4', text: '#ffffff' }
  return { fill: '#334155', stroke: '#94a3b8', text: '#ffffff' }
}

export function GraphExplorer({ filters }: { filters: GraphFilters }) {
  const [selectedNodeId, setSelectedNodeId] = useState('')
  const [includeRelationships, setIncludeRelationships] = useState(true)
  const [maxNodes, setMaxNodes] = useState(14)
  const [maxEdges, setMaxEdges] = useState(24)
  const [layoutMode, setLayoutMode] = useState<'radial' | 'linear'>('radial')
  const [showSuspiciousOnly, setShowSuspiciousOnly] = useState(false)
  const [selectedEdgeId, setSelectedEdgeId] = useState('')
  const [focusHistory, setFocusHistory] = useState<string[]>([])
  const [pinnedNodeIds, setPinnedNodeIds] = useState<string[]>([])

  const nodesQuery = useQuery({
    queryKey: ['investigation', 'graph-nodes', filters],
    queryFn: () => getGraphNodes({ ...filters, limit: 5000 }),
    staleTime: 30_000,
  })
  const findingsQuery = useQuery({
    queryKey: ['investigation', 'graph-findings', filters],
    queryFn: () => getGraphFindings({ ...filters, limit: 5000 }),
    staleTime: 30_000,
  })

  const nodeItems = nodesQuery.data?.items || []
  const findings = findingsQuery.data?.items || []

  useEffect(() => {
    if (selectedNodeId) return
    const suspiciousFirst = findings
      .flatMap((row: any) => String(row.subject_node_ids || '').split('|').filter(Boolean))
      .find(Boolean)
    const firstNode = suspiciousFirst || nodeItems.find((row: any) => row.node_type === 'Account')?.node_id || nodeItems[0]?.node_id || ''
    if (firstNode) setSelectedNodeId(firstNode)
  }, [findings, nodeItems, selectedNodeId])

  useEffect(() => {
    if (!selectedNodeId) return
    setFocusHistory((state) => {
      const next = [...state.filter((value) => value !== selectedNodeId), selectedNodeId]
      return next.slice(-8)
    })
  }, [selectedNodeId])

  const neighborhoodQuery = useQuery({
    queryKey: ['investigation', 'graph-neighborhood', selectedNodeId, filters, includeRelationships, maxNodes, maxEdges],
    queryFn: () =>
      getGraphNeighborhood(selectedNodeId, {
        ...filters,
        limit: 5000,
        include_relationships: includeRelationships,
        max_nodes: maxNodes,
        max_edges: maxEdges,
      }),
    enabled: !!selectedNodeId,
    staleTime: 30_000,
  })

  const suspiciousNodeIds = useMemo(() => {
    const ids = new Set<string>()
    findings.forEach((row: any) => {
      String(row.subject_node_ids || '')
        .split('|')
        .filter(Boolean)
        .forEach((value) => ids.add(value))
    })
    return ids
  }, [findings])

  const neighborhoodNodes = neighborhoodQuery.data?.nodes || []
  const neighborhoodEdges = neighborhoodQuery.data?.edges || []
  const highlightedNodeIds = new Set<string>(neighborhoodQuery.data?.suspicious_node_ids || [])
  const findingsByNode = neighborhoodQuery.data?.findings_by_node || {}
  const graphMeta = neighborhoodQuery.data?.graph_meta || {}
  const queryMeta = neighborhoodQuery.data?.query_meta || nodesQuery.data?.meta || findingsQuery.data?.meta || {}
  const selectedEdge = neighborhoodEdges.find((row: any) => row.edge_id === selectedEdgeId)
  const visibleNodes = useMemo(() => {
    if (!showSuspiciousOnly) return neighborhoodNodes
    return neighborhoodNodes.filter((row: any) => highlightedNodeIds.has(row.node_id) || row.node_id === selectedNodeId)
  }, [highlightedNodeIds, neighborhoodNodes, selectedNodeId, showSuspiciousOnly])

  const positionedNodes = useMemo(() => {
    if (!selectedNodeId || !visibleNodes.length) return []
    const width = 720
    const height = 360
    const centerX = width / 2
    const centerY = height / 2
    const centerNode = visibleNodes.find((row: any) => row.node_id === selectedNodeId)
    const others = visibleNodes.filter((row: any) => row.node_id !== selectedNodeId)
    const radius = Math.min(145, 55 + others.length * 10)

    const placed = []
    if (centerNode) {
      placed.push({ ...centerNode, x: centerX, y: centerY, isCenter: true })
    }
    if (layoutMode === 'linear') {
      others.forEach((row: any, index: number) => {
        const step = height / (others.length + 1)
        placed.push({
          ...row,
          x: centerX + 190,
          y: step * (index + 1),
          isCenter: false,
        })
      })
    } else {
      others.forEach((row: any, index: number) => {
        const angle = (Math.PI * 2 * index) / Math.max(others.length, 1)
        placed.push({
          ...row,
          x: centerX + Math.cos(angle) * radius,
          y: centerY + Math.sin(angle) * radius,
          isCenter: false,
        })
      })
    }
    return placed
  }, [layoutMode, visibleNodes, selectedNodeId])

  const nodePos = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>()
    positionedNodes.forEach((row: any) => map.set(row.node_id, { x: row.x, y: row.y }))
    return map
  }, [positionedNodes])

  const selectedNode = nodeItems.find((row: any) => row.node_id === selectedNodeId) || neighborhoodNodes.find((row: any) => row.node_id === selectedNodeId)
  const pinnedNodes = nodeItems.filter((row: any) => pinnedNodeIds.includes(row.node_id))
  const visibleNodeIds = new Set(positionedNodes.map((row: any) => row.node_id))
  const visibleEdges = neighborhoodEdges.filter((row: any) => visibleNodeIds.has(row.from_node_id) && visibleNodeIds.has(row.to_node_id))

  function togglePin(nodeId: string) {
    setPinnedNodeIds((state) => (state.includes(nodeId) ? state.filter((value) => value !== nodeId) : [...state, nodeId].slice(-8)))
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[320px,1fr]">
      <Card className="space-y-3">
        <CardTitle>Suspicious Nodes</CardTitle>
        <div className="space-y-2">
          {findings.slice(0, 10).map((row: any) => {
            const firstNode = String(row.subject_node_ids || '').split('|').find(Boolean) || ''
            return (
              <button
                key={row.finding_id}
                type="button"
                onClick={() => firstNode && setSelectedNodeId(firstNode)}
                className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-left hover:border-accent"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-text">{row.summary}</div>
                  <Badge variant={row.severity === 'high' ? 'red' : 'yellow'}>{row.severity}</Badge>
                </div>
                <div className="mt-1 text-xs text-text2">{String(row.reason_codes || '').replaceAll('|', ' · ')}</div>
              </button>
            )
          })}
          {findings.length === 0 && <div className="text-sm text-muted">No suspicious findings in the current filter scope.</div>}
        </div>

        <div className="border-t border-border pt-3">
          <CardTitle>Node List</CardTitle>
          <div className="mt-2 max-h-80 space-y-2 overflow-auto">
            {nodeItems.slice(0, 30).map((row: any) => (
              <button
                key={row.node_id}
                type="button"
                onClick={() => setSelectedNodeId(row.node_id)}
                className={`w-full rounded-lg border px-3 py-2 text-left ${
                  selectedNodeId === row.node_id ? 'border-accent bg-surface2' : 'border-border bg-surface'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-text">{row.label || row.node_id}</div>
                  <div className="flex items-center gap-2">
                    {pinnedNodeIds.includes(row.node_id) && <Badge variant="blue">pinned</Badge>}
                    {suspiciousNodeIds.has(row.node_id) && <Badge variant="yellow">flagged</Badge>}
                  </div>
                </div>
                <div className="mt-1 text-xs text-muted">{row.node_type} · {row.node_id}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-border pt-3">
          <CardTitle>Pinned Nodes</CardTitle>
          <div className="mt-2 space-y-2">
            {pinnedNodes.map((row: any) => (
              <button
                key={row.node_id}
                type="button"
                onClick={() => setSelectedNodeId(row.node_id)}
                className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-left"
              >
                <div className="text-sm font-medium text-text">{row.label || row.node_id}</div>
                <div className="mt-1 text-xs text-muted">{row.node_type}</div>
              </button>
            ))}
            {pinnedNodes.length === 0 && <div className="text-sm text-muted">Pin key accounts or counterparties for quick recall.</div>}
          </div>
        </div>
      </Card>

      <div className="space-y-4">
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <CardTitle>Graph Explorer</CardTitle>
            {selectedNodeId && (
              <Button variant="outline" onClick={() => setSelectedNodeId('')}>
                Reset Focus
              </Button>
            )}
          </div>
          <div className="text-sm text-text2">
            Click any suspicious item or node to expand its neighborhood. Red nodes are suspicious, gold is the current focus.
          </div>

          <div className="grid gap-3 rounded-xl border border-border bg-surface px-3 py-3 lg:grid-cols-[repeat(4,minmax(0,1fr))]">
            <label className="space-y-1 text-sm text-text">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Node Density</div>
              <select
                value={maxNodes}
                onChange={(event) => setMaxNodes(Number(event.target.value))}
                className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent"
              >
                {[8, 12, 14, 18, 24].map((value) => (
                  <option key={value} value={value}>{value} nodes</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm text-text">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Edge Density</div>
              <select
                value={maxEdges}
                onChange={(event) => setMaxEdges(Number(event.target.value))}
                className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent"
              >
                {[12, 18, 24, 32, 40].map((value) => (
                  <option key={value} value={value}>{value} edges</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm text-text">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Relationships</div>
              <select
                value={includeRelationships ? 'all' : 'flow-only'}
                onChange={(event) => setIncludeRelationships(event.target.value === 'all')}
                className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent"
              >
                <option value="all">All relationships</option>
                <option value="flow-only">Transaction flow only</option>
              </select>
            </label>
            <label className="space-y-1 text-sm text-text">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Layout</div>
              <select
                value={layoutMode}
                onChange={(event) => setLayoutMode(event.target.value as 'radial' | 'linear')}
                className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text outline-none focus:border-accent"
              >
                <option value="radial">Radial</option>
                <option value="linear">Linear</option>
              </select>
            </label>
            <div className="space-y-1 text-sm text-text">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Graph Query</div>
              <div className="rounded-lg border border-border bg-surface2 px-3 py-2 text-sm text-text2">
                Loaded {queryMeta.transactions_loaded || 0} transactions
                {queryMeta.cache_hit ? ' · cached' : ''}
                {queryMeta.truncated ? ' · limit capped' : ''}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant={showSuspiciousOnly ? 'primary' : 'outline'} onClick={() => setShowSuspiciousOnly((value) => !value)}>
              {showSuspiciousOnly ? 'Show all nodes' : 'Suspicious only'}
            </Button>
            <Button variant="outline" onClick={() => setSelectedEdgeId('')}>
              Clear edge selection
            </Button>
          </div>

          {(graphMeta.hidden_node_count || queryMeta.truncated) ? (
            <div className="rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
              Explorer is showing a focused subset to keep the graph readable.
              {graphMeta.hidden_node_count ? ` Hidden neighbors: ${graphMeta.hidden_node_count}.` : ''}
              {queryMeta.truncated ? ` Requested scope exceeded the safe limit of ${queryMeta.effective_limit}.` : ''}
            </div>
          ) : null}

          <div className="rounded-xl border border-border bg-surface2 p-3">
            <svg viewBox="0 0 720 360" className="h-[360px] w-full">
              {visibleEdges.map((edge: any) => {
                const from = nodePos.get(edge.from_node_id)
                const to = nodePos.get(edge.to_node_id)
                if (!from || !to) return null
                return (
                  <line
                    key={edge.edge_id}
                    onClick={() => setSelectedEdgeId(edge.edge_id)}
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke={selectedEdgeId === edge.edge_id ? '#f59e0b' : edge.edge_type === 'POSSIBLE_SAME_AS' ? '#a855f7' : '#64748b'}
                    strokeWidth={selectedEdgeId === edge.edge_id ? 4 : edge.edge_type === 'DERIVED_ACCOUNT_TO_ACCOUNT' ? 3 : 2}
                    opacity="0.9"
                    className="cursor-pointer"
                  />
                )
              })}
              {positionedNodes.map((node: any) => {
                const suspicious = highlightedNodeIds.has(node.node_id)
                const tone = nodeTone(node.node_type, suspicious, node.isCenter)
                return (
                  <g key={node.node_id} onClick={() => setSelectedNodeId(node.node_id)} className="cursor-pointer">
                    <circle cx={node.x} cy={node.y} r={node.isCenter ? 28 : 22} fill={tone.fill} stroke={tone.stroke} strokeWidth="3" />
                    <text x={node.x} y={node.y + 4} textAnchor="middle" fontSize="10" fill={tone.text}>
                      {shortLabel(node.label || node.node_id)}
                    </text>
                  </g>
                )
              })}
            </svg>
          </div>
        </Card>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="space-y-3">
            <CardTitle>Focused Node</CardTitle>
            {selectedNode ? (
              <div className="space-y-2">
                <div className="text-base font-semibold text-text">{selectedNode.label || selectedNode.node_id}</div>
                <div className="text-xs text-muted">{selectedNode.node_type} · {selectedNode.node_id}</div>
                <div className="flex flex-wrap gap-2">
                  {highlightedNodeIds.has(selectedNode.node_id) && <Badge variant="yellow">Suspicious</Badge>}
                  {pinnedNodeIds.includes(selectedNode.node_id) && <Badge variant="blue">Pinned</Badge>}
                  {selectedNode.review_status && <Badge variant="gray">{selectedNode.review_status}</Badge>}
                </div>
                <div className="text-sm text-text2">Source transactions: {selectedNode.source_transaction_ids || '—'}</div>
                <div className="text-sm text-text2">Files: {selectedNode.source_files || '—'}</div>
                <div className="flex flex-wrap gap-2 pt-2">
                  <Button variant="outline" size="sm" onClick={() => togglePin(selectedNode.node_id)}>
                    {pinnedNodeIds.includes(selectedNode.node_id) ? 'Unpin node' : 'Pin node'}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted">Select a node to inspect its neighborhood.</div>
            )}
          </Card>

          <Card className="space-y-3">
            <CardTitle>Node Findings</CardTitle>
            <div className="space-y-2">
              {selectedNodeId && (findingsByNode[selectedNodeId] || []).map((row: any) => (
                <div key={row.finding_id} className="rounded-lg border border-border bg-surface2 px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-text">{row.rule_type}</div>
                    <Badge variant={row.severity === 'high' ? 'red' : 'yellow'}>{row.severity}</Badge>
                  </div>
                  <div className="mt-1 text-sm text-text2">{row.summary}</div>
                </div>
              ))}
              {(!selectedNodeId || !(findingsByNode[selectedNodeId] || []).length) && (
                <div className="text-sm text-muted">No suspicious findings tied directly to the selected node.</div>
              )}
            </div>
          </Card>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="space-y-3">
            <CardTitle>Focus History</CardTitle>
            <div className="space-y-2">
              {focusHistory.slice().reverse().map((nodeId) => (
                <button
                  key={nodeId}
                  type="button"
                  onClick={() => setSelectedNodeId(nodeId)}
                  className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-left text-sm text-text hover:border-accent"
                >
                  {nodeId}
                </button>
              ))}
              {focusHistory.length === 0 && <div className="text-sm text-muted">Recent graph focus targets will appear here.</div>}
            </div>
          </Card>

          <Card className="space-y-3">
            <CardTitle>Selected Relationship</CardTitle>
            {selectedEdge ? (
              <div className="space-y-2 text-sm text-text2">
                <div className="font-medium text-text">{selectedEdge.edge_type}</div>
                <div>{selectedEdge.from_node_id} → {selectedEdge.to_node_id}</div>
                <div>Aggregation: {selectedEdge.aggregation_level || 'graph'}</div>
                <div>Amount: {selectedEdge.amount_display || selectedEdge.amount || '—'}</div>
                <div>Transactions: {selectedEdge.source_transaction_ids || selectedEdge.transaction_id || '—'}</div>
              </div>
            ) : (
              <div className="text-sm text-muted">Select an edge in the canvas or from the visible relationships list.</div>
            )}
          </Card>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="space-y-3">
            <CardTitle>Visible Relationships</CardTitle>
            <div className="max-h-72 space-y-2 overflow-auto">
              {visibleEdges.slice(0, 20).map((row: any) => (
                <button
                  key={row.edge_id}
                  type="button"
                  onClick={() => setSelectedEdgeId(row.edge_id)}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${
                    selectedEdgeId === row.edge_id ? 'border-accent bg-surface' : 'border-border bg-surface2'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-text">{row.edge_type}</div>
                    <Badge variant={row.edge_type === 'POSSIBLE_SAME_AS' ? 'yellow' : 'blue'}>
                      {row.aggregation_level || 'graph'}
                    </Badge>
                  </div>
                  <div className="mt-1 text-text2">{row.from_node_id} → {row.to_node_id}</div>
                </button>
              ))}
              {visibleEdges.length === 0 && <div className="text-sm text-muted">No visible relationships in the current focused neighborhood.</div>}
            </div>
          </Card>

          <Card className="space-y-3">
            <CardTitle>Hidden Neighbors</CardTitle>
            <div className="space-y-2 text-sm text-text2">
              <div>Hidden node count: {graphMeta.hidden_node_count || 0}</div>
              <div>Hidden finding count: {graphMeta.hidden_findings_count || 0}</div>
            </div>
            <div className="max-h-56 space-y-2 overflow-auto">
              {(graphMeta.hidden_node_ids || []).map((nodeId: string) => (
                <button
                  key={nodeId}
                  type="button"
                  onClick={() => setSelectedNodeId(nodeId)}
                  className="w-full rounded-lg border border-border bg-surface2 px-3 py-2 text-left text-sm text-text hover:border-accent"
                >
                  {nodeId}
                </button>
              ))}
              {(!graphMeta.hidden_node_ids || graphMeta.hidden_node_ids.length === 0) && (
                <div className="text-sm text-muted">No hidden neighbors in the current view.</div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
