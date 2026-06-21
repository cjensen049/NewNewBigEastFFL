/**
 * Transactions.jsx — Trades and Waiver Wire page.
 *
 * Tabs: Trade Tree | Trade Log | Waivers | Tendencies
 */
import { useState, useRef, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { TabBar, TabPanel } from '../components/Tabs'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'

// ─── Position colour helpers (used in Waivers tab) ───────────────────────────

const WAV_POS_ROW = {
  QB: { borderLeft: '3px solid #ef4444', background: 'rgba(127,29,29,0.18)' },
  RB: { borderLeft: '3px solid #22c55e', background: 'rgba(20,83,45,0.18)' },
  WR: { borderLeft: '3px solid #3b82f6', background: 'rgba(30,58,138,0.18)' },
  TE: { borderLeft: '3px solid #f97316', background: 'rgba(124,45,18,0.18)' },
}
const WAV_POS_BADGE = {
  QB: { background: '#b91c1c', color: '#fff' },
  RB: { background: '#15803d', color: '#fff' },
  WR: { background: '#1d4ed8', color: '#fff' },
  TE: { background: '#c2410c', color: '#fff' },
}
function WavPosBadge({ pos }) {
  if (!pos) return null
  const s = WAV_POS_BADGE[pos] ?? { background: '#374151', color: '#fff' }
  return (
    <span style={{ ...s, borderRadius: '3px', padding: '1px 6px', fontSize: '11px', fontWeight: 700 }}>
      {pos}
    </span>
  )
}

const TABS = [
  { id: 'tree',        label: 'Trade Tree' },
  { id: 'log',         label: 'Trade Log' },
  { id: 'waivers',     label: 'Waivers' },
  { id: 'tendencies',  label: 'Tendencies' },
]

// ---------------------------------------------------------------------------
// Trade Tree — visual node graph
// ---------------------------------------------------------------------------

// Color scheme matching the original Streamlit Graphviz visualization
const NODE_STYLES = {
  root:   { background: '#1a472a', border: '2px solid #2d6a4f' },
  player: { background: '#154360', border: '2px solid #1a6090' },
  pick:   { background: '#6e2c00', border: '2px solid #a04000' },
  draft:  { background: '#7d5a00', border: '2px solid #a67c00' },
}

// Custom ReactFlow node — a colored rounded box with optional expand/collapse button
function TradeNode({ data }) {
  const style = NODE_STYLES[data.nodeType] ?? NODE_STYLES.player
  return (
    <div
      style={style}
      className="rounded-lg px-3 py-2 text-white text-xs min-w-[170px] max-w-[240px]"
    >
      <Handle type="target" position={Position.Left} style={{ background: '#6b7280' }} />
      <div className="whitespace-pre-line leading-snug">{data.label}</div>
      {/* Expand/collapse button shown only on nodes with hidden or shown sub-trades */}
      {data.expandable && (
        <button
          onClick={(e) => { e.stopPropagation(); data.onToggle() }}
          className="mt-1.5 w-full text-center text-gray-300 hover:text-white text-xs bg-black/30 hover:bg-black/50 rounded px-1 py-0.5 cursor-pointer transition-colors"
        >
          {data.expanded ? '▲ collapse' : `▶ ${data.childCount} more`}
        </button>
      )}
      <Handle type="source" position={Position.Right} style={{ background: '#6b7280' }} />
    </div>
  )
}

// Register the custom node type with ReactFlow
const nodeTypes = { tradeNode: TradeNode }

/**
 * Convert the API's recursive tree into ReactFlow's flat nodes + edges arrays.
 *
 * Layout: Graphviz-style left-to-right centering (leaves claim sequential y slots,
 * internal nodes center between their outermost children).
 *
 * Depth expansion:
 *   - Depth ≤ 2 always renders (root → trade → counter-assets → direct results).
 *   - Depth 3+ only renders if the parent path is in expandedPaths.
 *   - Collapsed nodes show an expand button with the hidden child count.
 */
function buildGraph(playerName, tradeNode, expandedPaths, onToggle) {
  const nodes = []
  const edges = []
  let leafIndex = 0
  const X_GAP = 280
  const Y_GAP = 110

  function makeLabel(apiNode) {
    if (apiNode.asset_type === 'player') {
      return `S${apiNode.season} Wk${apiNode.week}\n${apiNode.from_owner} → ${apiNode.to_owner}\n${apiNode.asset_name}`
    } else if (apiNode.asset_type === 'pick') {
      const draftedCount = (apiNode.children ?? []).filter(c => c.asset_type === 'draft').length
      let lbl = `${apiNode.asset_name}\n${apiNode.from_owner} → ${apiNode.to_owner}`
      return lbl + (draftedCount ? `\n(${draftedCount} drafted)` : '\n(future / no data)')
    } else {
      return `Drafted: ${apiNode.asset_name}\n${apiNode.to_owner} (${apiNode.season})`
    }
  }

  // path is a stable string key for this node used for expansion state (e.g. "trade_0_2_1")
  function traverse(apiNode, parentId, depth, path) {
    const children = apiNode.children ?? []
    const autoExpand = depth <= 2          // always show depths 1-3 (relative to root=0)
    const userExpanded = expandedPaths.has(path)
    const showChildren = children.length > 0 && (autoExpand || userExpanded)

    let y
    if (showChildren) {
      const childYs = children.map((child, i) =>
        traverse(child, path, depth + 1, `${path}_${i}`)
      )
      y = (childYs[0] + childYs[childYs.length - 1]) / 2
    } else {
      y = leafIndex++ * Y_GAP
    }

    // Only nodes at depth > 2 with children get an expand toggle
    const expandable = children.length > 0 && !autoExpand
    const capturedPath = path

    nodes.push({
      id: path,
      type: 'tradeNode',
      position: { x: depth * X_GAP, y },
      data: {
        label: makeLabel(apiNode),
        nodeType: apiNode.asset_type,
        expandable,
        expanded: userExpanded,
        childCount: children.length,
        onToggle: expandable ? () => onToggle(capturedPath) : undefined,
      },
    })

    if (parentId) {
      edges.push({
        id: `e-${parentId}-${path}`,
        source: parentId,
        target: path,
        type: 'smoothstep',
        style: { stroke: '#6b7280', strokeWidth: 1.5 },
      })
    }

    return y
  }

  const rootY = traverse(tradeNode, 'root', 1, 'trade')

  nodes.push({
    id: 'root',
    type: 'tradeNode',
    position: { x: 0, y: rootY },
    data: { label: playerName, nodeType: 'root', expandable: false },
  })

  return { nodes, edges, leafCount: leafIndex }
}

function TradeTreeTab() {
  const [playerInput, setPlayerInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [selectedTradeIdx, setSelectedTradeIdx] = useState(0)
  const [expandedPaths, setExpandedPaths] = useState(new Set())
  const inputRef = useRef(null)
  const dropdownRef = useRef(null)

  const { data: playersData } = useQuery({
    queryKey: ['traded-players'],
    queryFn: () => fetch('/api/transactions/traded-players').then(r => r.json()),
  })

  const allPlayers = playersData?.players ?? []

  // Filter to at most 10 matching players as the user types
  const filteredPlayers = useMemo(() => {
    const q = playerInput.trim().toLowerCase()
    if (!q) return []
    return allPlayers.filter(p => p.toLowerCase().includes(q)).slice(0, 10)
  }, [playerInput, allPlayers])

  const { data: treeData, isLoading } = useQuery({
    queryKey: ['trade-tree', searchQuery],
    queryFn: () =>
      fetch(`/api/transactions/trade-tree/${encodeURIComponent(searchQuery)}`).then(r => r.json()),
    enabled: !!searchQuery,
  })

  // Close dropdown when clicking outside both input and dropdown
  useEffect(() => {
    function handleClickOutside(e) {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target) &&
        inputRef.current && !inputRef.current.contains(e.target)
      ) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSearch = (query) => {
    const q = (query ?? playerInput).trim()
    if (!q) return
    if (q !== searchQuery) {
      setSelectedTradeIdx(0)
      setExpandedPaths(new Set())
    }
    setSearchQuery(q)
    setShowDropdown(false)
  }

  const handleSelectPlayer = (player) => {
    setPlayerInput(player)
    setShowDropdown(false)
    handleSearch(player)
  }

  const handleTradeChange = (i) => {
    setSelectedTradeIdx(i)
    setExpandedPaths(new Set())
  }

  const togglePath = (path) => {
    setExpandedPaths(prev => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const trades = treeData?.trades ?? []
  const activeTrade = trades[selectedTradeIdx] ?? null

  const { nodes, edges, leafCount = 1 } = activeTrade
    ? buildGraph(treeData.player, activeTrade, expandedPaths, togglePath)
    : { nodes: [], edges: [], leafCount: 1 }

  return (
    <div>
      {/* Search input with custom dropdown */}
      <div style={{ marginBottom: '20px' }}>
        <p style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '8px' }}>Search Player</p>
        <div style={{ display: 'flex', gap: '8px', maxWidth: '480px' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <input
              ref={inputRef}
              value={playerInput}
              onChange={e => { setPlayerInput(e.target.value); setShowDropdown(true) }}
              onKeyDown={e => {
                if (e.key === 'Enter') handleSearch()
                if (e.key === 'Escape') setShowDropdown(false)
              }}
              onFocus={e => { e.target.style.borderColor = 'var(--brand-navy)'; if (playerInput.trim()) setShowDropdown(true) }}
              placeholder="Type a player name..."
              className="search-input"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-mid)',
                borderRadius: '8px',
                padding: '10px 14px',
                width: '100%',
                color: 'var(--text-primary)',
                fontSize: '13px',
                fontFamily: 'var(--font-body)',
                outline: 'none',
                transition: 'border-color 0.15s',
                boxSizing: 'border-box',
              }}
              onBlur={e => { e.target.style.borderColor = 'var(--border-mid)' }}
            />
            {/* Custom dropdown */}
            {showDropdown && filteredPlayers.length > 0 && (
              <div
                ref={dropdownRef}
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 4px)',
                  left: 0,
                  right: 0,
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-mid)',
                  borderRadius: '8px',
                  maxHeight: '280px',
                  overflowY: 'auto',
                  zIndex: 50,
                  boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                }}
              >
                {filteredPlayers.map((p, idx) => (
                  <button
                    key={p}
                    onMouseDown={e => { e.preventDefault(); handleSelectPlayer(p) }}
                    style={{
                      display: 'block',
                      width: '100%',
                      padding: '9px 14px',
                      textAlign: 'left',
                      background: 'none',
                      border: 'none',
                      borderBottom: idx < filteredPlayers.length - 1 ? '1px solid var(--border)' : 'none',
                      color: 'var(--text-primary)',
                      fontSize: '13px',
                      fontFamily: 'var(--font-body)',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-raised)' }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'none' }}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={() => handleSearch()}
            style={{
              background: 'var(--brand-navy)',
              border: '1px solid var(--border-mid)',
              borderRadius: '8px',
              padding: '10px 18px',
              color: 'var(--text-primary)',
              fontSize: '13px',
              fontWeight: 600,
              fontFamily: 'var(--font-body)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            Search
          </button>
        </div>
      </div>

      {/* Empty state — shown when no search has been submitted */}
      {!searchQuery && !treeData && (
        <div style={{ textAlign: 'center', padding: '60px 20px' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
          <p className="fs-title" style={{ color: 'var(--text-muted)' }}>
            Search for a player to trace their trade history
          </p>
        </div>
      )}

      {isLoading && <LoadingSpinner />}

      {treeData && !isLoading && (
        <>
          <h2 className="text-base md:text-lg font-semibold mb-1">{treeData.player} — Trade Tree</h2>
          <p className="text-xs md:text-sm text-gray-500 mb-3">{trades.length} trade(s) in league history</p>

          {trades.length === 0 ? (
            <p className="text-gray-500 italic">No recorded trades for this player.</p>
          ) : (
            <>
              {/* Trade selector when player was traded multiple times */}
              {trades.length > 1 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {trades.map((t, i) => (
                    <button
                      key={i}
                      onClick={() => handleTradeChange(i)}
                      className={`px-3 py-1 text-sm rounded border transition-colors ${
                        selectedTradeIdx === i
                          ? 'bg-emerald-700 border-emerald-600 text-white'
                          : 'border-gray-600 text-gray-400 hover:border-gray-500'
                      }`}
                    >
                      S{t.season} Wk{t.week}: {t.from_owner} → {t.to_owner}
                    </button>
                  ))}
                </div>
              )}

              {/* ReactFlow graph — height scales with leaf count (leaves drive vertical space) */}
              <div
                className="rounded border border-gray-700 bg-gray-950"
                style={{ height: Math.max(320, Math.min(680, leafCount * 110 + 120)) }}
              >
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  nodeTypes={nodeTypes}
                  fitView
                  fitViewOptions={{ padding: 0.2 }}
                  proOptions={{ hideAttribution: true }}
                  minZoom={0.3}
                  maxZoom={2}
                >
                  <Background color="#374151" gap={24} />
                  <Controls showInteractive={false} />
                </ReactFlow>
              </div>

              {/* Text summary below the graph */}
              {activeTrade && (() => {
                const children = activeTrade.children ?? []
                // Split assets by direction: same side as the selected player vs opposite
                const sentWith = children.filter(c => c.from_owner === activeTrade.from_owner)
                const received = children.filter(c => c.from_owner !== activeTrade.from_owner)

                function assetLine(c) {
                  const picks = c.asset_type === 'pick'
                    ? c.children?.filter(g => g.asset_type === 'draft').map(g => g.asset_name)
                    : []
                  return (
                    <span>
                      <strong>{c.asset_name}</strong>
                      {picks?.length > 0 && (
                        <span className="text-gray-400"> — used on: {picks.join(', ')}</span>
                      )}
                    </span>
                  )
                }

                return (
                  <div className="mt-4 rounded border border-gray-700 p-4 text-sm space-y-3">
                    <p className="font-medium">
                      S{activeTrade.season} Wk{activeTrade.week}:{' '}
                      <span className="text-blue-300">{activeTrade.from_owner}</span>
                      {' '}traded to{' '}
                      <span className="text-red-300">{activeTrade.to_owner}</span>
                    </p>

                    <div>
                      <p className="text-gray-400 mb-1 text-xs uppercase tracking-wide">
                        {activeTrade.from_owner} sent
                      </p>
                      <ul className="space-y-0.5 text-gray-200">
                        <li className="pl-3">• <strong>{treeData.player}</strong></li>
                        {sentWith.map((c, i) => (
                          <li key={i} className="pl-3">• {assetLine(c)}</li>
                        ))}
                      </ul>
                    </div>

                    {received.length > 0 && (
                      <div>
                        <p className="text-gray-400 mb-1 text-xs uppercase tracking-wide">
                          {activeTrade.to_owner} sent back
                        </p>
                        <ul className="space-y-0.5 text-gray-200">
                          {received.map((c, i) => (
                            <li key={i} className="pl-3">• {assetLine(c)}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )
              })()}
            </>
          )}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Trade Log tab
// ---------------------------------------------------------------------------

// Groups players and picks by direction (from_owner → to_owner) for a single trade.
// Returns an array of { from, to, players: string[], picks: string[] }.
function groupTradeDirections(players, picks) {
  const map = new Map()
  const key = (p) => `${p.from_owner}|||${p.to_owner}`
  const ensure = (p) => {
    if (!map.has(key(p))) map.set(key(p), { from: p.from_owner, to: p.to_owner, players: [], picks: [] })
    return map.get(key(p))
  }
  players.forEach(p => ensure(p).players.push(p.name))
  picks.forEach(p => ensure(p).picks.push(p.name))
  return [...map.values()]
}

function TradeLogTab() {
  const { data: ownersData } = useQuery({
    queryKey: ['owners-list'],
    queryFn: () => fetch('/api/owners/').then(r => r.json()),
  })

  const { data: seasonsData } = useQuery({
    queryKey: ['history-seasons'],
    queryFn: () => fetch('/api/history/seasons').then(r => r.json()),
  })

  const owners = ownersData?.owners ?? []
  const seasons = seasonsData?.seasons ?? []

  const [ownerFilter, setOwnerFilter]   = useState('')
  const [seasonFilter, setSeasonFilter] = useState('')
  const [sortKey, setSortKey]           = useState('season')
  const [sortDir, setSortDir]           = useState('desc')

  const params = new URLSearchParams()
  if (ownerFilter)  params.set('owner',  ownerFilter)
  if (seasonFilter) params.set('season', seasonFilter)

  const { data, isLoading } = useQuery({
    queryKey: ['trade-log', ownerFilter, seasonFilter],
    queryFn: () => fetch(`/api/transactions/trades?${params}`).then(r => r.json()),
  })

  const trades = data?.trades ?? []

  const sorted = [...trades].sort((a, b) => {
    const cmp = sortKey === 'week'
      ? (a.season - b.season || a.week - b.week)
      : (a.season - b.season || a.week - b.week)
    return sortDir === 'asc' ? cmp : -cmp
  })

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const TH = ({ children, colKey, align = 'left' }) => {
    const active = sortKey === colKey
    return (
      <th
        onClick={colKey ? () => handleSort(colKey) : undefined}
        style={{
          padding: '8px 12px', fontSize: '11px', fontWeight: 600, letterSpacing: '1px',
          textTransform: 'uppercase', background: 'var(--bg-page)', whiteSpace: 'nowrap',
          borderBottom: '1px solid var(--border)', textAlign: align,
          cursor: colKey ? 'pointer' : 'default', userSelect: 'none',
          color: active ? 'var(--text-primary)' : 'var(--text-faint)',
        }}
      >
        {children}
        {colKey && (
          <span style={{ marginLeft: '4px', opacity: active ? 1 : 0.4, fontSize: '9px' }}>
            {active ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
          </span>
        )}
      </th>
    )
  }

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-5">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Season:</label>
          <select
            value={seasonFilter}
            onChange={e => setSeasonFilter(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="">All</option>
            {seasons.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Owner:</label>
          <select
            value={ownerFilter}
            onChange={e => setOwnerFilter(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="">All</option>
            {owners.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
      </div>

      {isLoading ? <LoadingSpinner /> : (
        <>
          <p className="text-xs md:text-sm text-gray-500 mb-3">{sorted.length} trades</p>
          <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
            <div style={{ overflowY: 'auto', maxHeight: '600px' }}>
              <table className="nnbe-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <TH colKey="season">Season</TH>
                    <TH colKey="week" align="right">Wk</TH>
                    <TH>Trade</TH>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((t, i) => {
                    const dirs = groupTradeDirections(t.players, t.picks)
                    return (
                      <tr key={i} className="standings-row" style={{ borderBottom: '1px solid var(--border)', verticalAlign: 'top' }}>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{t.season}</td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{t.week}</td>
                        <td style={{ padding: '8px 12px' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(dirs.length, 2)}, 1fr)`, gap: '0 16px' }}>
                            {dirs.map((dir, di) => (
                              <div key={di} style={{ borderLeft: di > 0 ? '1px solid var(--border)' : 'none', paddingLeft: di > 0 ? '16px' : 0 }}>
                                {/* Direction header: From → To */}
                                <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '4px' }}>
                                  <span style={{ color: '#5b8dd9' }}>{dir.from}</span>
                                  <span style={{ color: 'var(--text-faint)', margin: '0 5px' }}>→</span>
                                  <span style={{ color: 'var(--gold)' }}>{dir.to}</span>
                                </div>
                                {/* Players */}
                                {dir.players.map((name, pi) => (
                                  <div key={pi} style={{ paddingLeft: '8px', fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.7 }}>
                                    {name}
                                  </div>
                                ))}
                                {/* Picks */}
                                {dir.picks.map((name, pi) => (
                                  <div key={pi} style={{ paddingLeft: '8px', fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.7 }}>
                                    🏈 {name}
                                  </div>
                                ))}
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Waivers tab
// ---------------------------------------------------------------------------

function WaiversTab() {
  const { data: activityData, isLoading: loadAct } = useQuery({
    queryKey: ['waiver-activity'],
    queryFn: () => fetch('/api/transactions/waivers/activity').then(r => r.json()),
  })

  const { data: faabData, isLoading: loadFaab } = useQuery({
    queryKey: ['waiver-faab'],
    queryFn: () => fetch('/api/transactions/waivers/faab').then(r => r.json()),
  })

  const { data: playersData, isLoading: loadPlayers } = useQuery({
    queryKey: ['waiver-players'],
    queryFn: () => fetch('/api/transactions/waivers/players').then(r => r.json()),
  })

  const { data: bySeasonData } = useQuery({
    queryKey: ['waiver-by-season'],
    queryFn: () => fetch('/api/transactions/waivers/by-season').then(r => r.json()),
  })

  const [selectedSeason, setSelectedSeason] = useState(null)
  const allSeasons = bySeasonData?.seasons ?? []
  const activeSeason = selectedSeason ?? allSeasons[0]
  const seasonRows = (bySeasonData?.by_season ?? []).filter(r => r.season === activeSeason)

  if (loadAct || loadFaab || loadPlayers) return <LoadingSpinner />

  const activityRows = (activityData?.activity ?? []).map(o => ({
    owner: o.owner,
    waiver_claims: o.waiver_claims,
    drops: o.drops,
    faab_spent: `$${o.faab_spent}`,
    bid_win_pct: o.success_rate != null ? `${(o.success_rate * 100).toFixed(1)}%` : '—',
  }))

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-base md:text-lg font-semibold mb-1">Biggest FAAB Claims</h2>
        <p className="text-xs text-gray-500 mb-3">Top 20 successful FAAB bids of all time</p>
        <DataTable
          maxHeight="380px"
          defaultSort="amount"
          defaultDir="desc"
          rows={faabData?.top_bids?.slice(0, 20) ?? []}
          rowStyle={(b) => WAV_POS_ROW[b.position] ?? {}}
          columns={[
            { key: 'player', label: 'Player', render: v => <span style={{ fontWeight: 500 }}>{v}</span> },
            { key: 'position', label: 'Pos', sortable: false, render: v => <WavPosBadge pos={v} /> },
            { key: 'owner', label: 'Owner', render: v => <span style={{ color: 'var(--text-muted)' }}>{v}</span> },
            { key: 'season', label: 'Season', align: 'right', render: v => <span style={{ color: 'var(--text-muted)' }}>{v}</span> },
            { key: 'week', label: 'Wk', align: 'right', render: v => <span style={{ color: 'var(--text-muted)' }}>{v}</span> },
            { key: 'amount', label: 'FAAB', align: 'right', render: v => <span style={{ color: 'var(--green)', fontWeight: 600 }}>${v}</span> },
          ]}
        />
      </div>

      <div>
        <h2 className="text-base md:text-lg font-semibold mb-3">Owner Activity — All Time</h2>
        <DataTable
          rows={activityRows}
          maxHeight="460px"
          columns={[
            { key: 'owner',         label: 'Owner' },
            { key: 'waiver_claims', label: 'Waivers',  align: 'right' },
            { key: 'drops',         label: 'Drops',    align: 'right' },
            { key: 'faab_spent',    label: 'FAAB $',   align: 'right' },
            { key: 'bid_win_pct',   label: 'Bid Win%', align: 'right' },
          ]}
        />
      </div>

      <div>
        <div className="flex items-center gap-3 mb-3">
          <h2 className="text-base md:text-lg font-semibold">Activity by Season</h2>
          <select
            value={activeSeason ?? ''}
            onChange={e => setSelectedSeason(Number(e.target.value))}
            className="ml-2 bg-gray-800 border border-gray-600 rounded px-3 py-1 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
          >
            {allSeasons.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <DataTable
          rows={[...seasonRows].sort((a, b) => b.waiver_claims - a.waiver_claims)}
          maxHeight="460px"
          columns={[
            { key: 'owner',         label: 'Owner' },
            { key: 'waiver_claims', label: 'Waivers', align: 'right' },
            { key: 'drops',         label: 'Drops',   align: 'right' },
            { key: 'faab_spent',    label: 'FAAB $',  align: 'right' },
          ]}
        />
      </div>

      <div>
        <h2 className="text-base md:text-lg font-semibold mb-1">Revolving Door Players</h2>
        <p className="text-xs text-gray-500 mb-3">Players with the most total moves (adds + drops)</p>
        <DataTable
          maxHeight="440px"
          defaultSort="total_moves"
          defaultDir="desc"
          rows={playersData?.players?.slice(0, 20) ?? []}
          rowStyle={(p) => WAV_POS_ROW[p.position] ?? {}}
          columns={[
            { key: 'player', label: 'Player', render: v => <span style={{ fontWeight: 500 }}>{v}</span> },
            { key: 'position', label: 'Pos', sortable: false, render: v => <WavPosBadge pos={v} /> },
            { key: 'adds', label: 'Adds', align: 'right', render: v => <span style={{ color: 'var(--text-muted)' }}>{v}</span> },
            { key: 'drops', label: 'Drops', align: 'right', render: v => <span style={{ color: 'var(--text-muted)' }}>{v}</span> },
            { key: 'total_moves', label: 'Total', align: 'right', render: v => <span style={{ fontWeight: 600 }}>{v}</span> },
          ]}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tendencies tab
// ---------------------------------------------------------------------------

function TendenciesTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['trade-stats'],
    queryFn: () => fetch('/api/transactions/trade-stats').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />

  const stats = data?.stats ?? []
  const owners = data?.owners ?? []
  const heatmap = data?.heatmap ?? []
  const maxVal = Math.max(...heatmap.flat().filter(v => v > 0), 1)

  function heatColor(val) {
    if (val === 0) return 'bg-gray-800 text-gray-600'
    const intensity = val / maxVal
    if (intensity > 0.7) return 'bg-blue-600 text-white font-bold'
    if (intensity > 0.4) return 'bg-blue-700/70 text-blue-200'
    return 'bg-blue-900/40 text-blue-300'
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-base md:text-lg font-semibold mb-3">Trade Activity by Owner</h2>
        <DataTable
          rows={stats}
          maxHeight="460px"
          columns={[
            { key: 'owner',         label: 'Owner' },
            { key: 'total_trades',  label: 'Trades',      align: 'right' },
            { key: 'players_in',    label: 'Players In',  align: 'right' },
            { key: 'players_out',   label: 'Players Out', align: 'right' },
            { key: 'picks_in',      label: 'Picks In',    align: 'right' },
            { key: 'picks_out',     label: 'Picks Out',   align: 'right' },
            { key: 'waiver_claims', label: 'Waivers',     align: 'right' },
            { key: 'faab_spent',    label: 'FAAB $',      align: 'right' },
          ]}
        />
      </div>

      <div>
        <h2 className="text-base md:text-lg font-semibold mb-1">Trade Partner Frequency</h2>
        <p className="text-xs text-gray-500 mb-3">Number of trades between each pair</p>
        <div className="overflow-auto rounded border border-gray-700">
          <table className="text-xs text-gray-300">
            <thead className="bg-gray-800 text-gray-400">
              <tr>
                <th className="px-2 py-2 sticky left-0 bg-gray-800"></th>
                {owners.map(o => (
                  <th key={o} className="px-2 py-2 text-center whitespace-nowrap">{o}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700/50">
              {owners.map((row, ri) => (
                <tr key={row}>
                  <td className="px-2 py-1.5 sticky left-0 bg-gray-900 font-medium whitespace-nowrap">{row}</td>
                  {owners.map((col, ci) => {
                    const val = heatmap[ri]?.[ci] ?? 0
                    return (
                      <td key={col} className={`px-2 py-1.5 text-center ${heatColor(val)}`}>
                        {val || ''}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page assembly
// ---------------------------------------------------------------------------

const CONTAINER = { maxWidth: '1280px', margin: '0 auto', padding: '0 clamp(12px, 3vw, 24px)' }

export default function Transactions() {
  const [tab, setTab] = useState('tree')

  return (
    <div>
      {/* Full-width header */}
      <div style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
        <div style={{ ...CONTAINER, padding: '20px clamp(12px, 3vw, 24px) 0' }}>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '36px', letterSpacing: '2px', color: 'var(--text-primary)', lineHeight: 1, marginBottom: '4px' }}>
            Transactions
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '12px' }}>
            Trade trees, waiver wire activity, and transaction patterns across all seasons.
          </p>
          {/* Tab bar — flush to bottom of header */}
          <div style={{ display: 'flex', marginBottom: '-1px', overflowX: 'auto' }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} className={`owner-tab${tab === t.id ? ' active' : ''}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab content */}
      <div style={{ ...CONTAINER, padding: '24px clamp(12px, 3vw, 24px)' }}>
        <TabPanel id="tree"       activeTab={tab}><TradeTreeTab /></TabPanel>
        <TabPanel id="log"        activeTab={tab}><TradeLogTab /></TabPanel>
        <TabPanel id="waivers"    activeTab={tab}><WaiversTab /></TabPanel>
        <TabPanel id="tendencies" activeTab={tab}><TendenciesTab /></TabPanel>
      </div>
    </div>
  )
}
