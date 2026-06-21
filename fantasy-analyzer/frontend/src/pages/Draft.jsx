/**
 * Draft.jsx — draft history page.
 *
 * Tab 1 "By Owner": all picks for a selected owner with total fantasy points
 *   scored while that player was on their roster. Sorted by points desc by
 *   default so the best picks float to the top.
 *
 * Tab 2 "Draft Board": pick list for a selected season, grouped by round,
 *   color-coded by position. No horizontal scrolling.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { TabBar, TabPanel } from '../components/Tabs'
import DataTable from '../components/DataTable'

// ─── Position colours ────────────────────────────────────────────────────────
// Each position gets a left-border colour and a subtle row background tint.

const POS_STYLE = {
  QB: { border: 'border-l-red-500',    bg: 'bg-red-900/30' },
  RB: { border: 'border-l-green-500',  bg: 'bg-green-900/30' },
  WR: { border: 'border-l-blue-500',   bg: 'bg-blue-900/30' },
  TE: { border: 'border-l-orange-500', bg: 'bg-orange-900/30' },
}

const POS_BADGE = {
  QB: 'bg-red-700',
  RB: 'bg-green-700',
  WR: 'bg-blue-700',
  TE: 'bg-orange-600',
}

function posStyle(pos) {
  return POS_STYLE[pos] ?? { border: 'border-l-gray-600', bg: 'bg-gray-800/40' }
}

function PosBadge({ pos }) {
  if (!pos) return null
  const color = POS_BADGE[pos] ?? 'bg-gray-600'
  return (
    <span className={`${color} text-white text-xs font-bold px-1.5 py-0.5 rounded`}>
      {pos}
    </span>
  )
}

// ─── Tabs ────────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'owner', label: 'By Owner' },
  { id: 'board', label: 'Draft Board' },
]

// ─── Tab 1: By Owner ─────────────────────────────────────────────────────────

function ByOwnerTab() {
  const [selectedUserId, setSelectedUserId] = useState(null)

  // Fetch owners who have picks (for the dropdown)
  const { data: ownersData, isLoading: loadingOwners } = useQuery({
    queryKey: ['draft-owners'],
    queryFn: () => fetch('/api/draft/owners').then(r => r.json()),
  })

  const owners = ownersData?.owners ?? []
  const activeUserId = selectedUserId ?? owners[0]?.user_id ?? null

  // Fetch picks (with points) for the selected owner
  const { data: picksData, isLoading: loadingPicks } = useQuery({
    queryKey: ['draft-owner-picks', activeUserId],
    queryFn: () => fetch(`/api/draft/owner/${activeUserId}`).then(r => r.json()),
    enabled: activeUserId !== null,
  })

  if (loadingOwners) return <div className="text-gray-400">Loading owners…</div>

  const allPicks = picksData?.picks ?? []
  const totalPts = allPicks.reduce((s, p) => s + (p.points_on_team ?? 0), 0)

  return (
    <div>
      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="flex items-center gap-2">
          <label className="text-gray-400 text-sm">Owner</label>
          <select
            value={activeUserId ?? ''}
            onChange={e => setSelectedUserId(e.target.value)}
            className="bg-gray-700 border border-gray-600 text-white rounded px-3 py-1.5 text-sm"
          >
            {owners.map(o => (
              <option key={o.user_id} value={o.user_id}>{o.owner}</option>
            ))}
          </select>
        </div>

        {allPicks.length > 0 && (
          <span className="text-gray-500 text-sm ml-auto">
            {allPicks.length} picks · {totalPts.toFixed(1)} total pts on roster
          </span>
        )}
      </div>

      {loadingPicks && <div className="text-gray-400">Loading picks…</div>}

      {!loadingPicks && allPicks.length === 0 && (
        <div className="text-gray-500">No picks found.</div>
      )}

      {allPicks.length > 0 && (
        <DataTable
          defaultSort="points_on_team"
          defaultDir="desc"
          rows={allPicks}
          rowClassName={(p) => {
            const { border, bg } = posStyle(p.position)
            return `border-l-4 ${border} ${bg}`
          }}
          columns={[
            { key: 'player_name', label: 'Player' },
            { key: 'position', label: 'Pos', sortable: false, render: (v) => <PosBadge pos={v} /> },
            { key: 'season', label: 'Season', align: 'right' },
            { key: 'round', label: 'Rd', align: 'right' },
            { key: 'pick_no', label: 'Pick', align: 'right' },
            {
              key: 'total_points', label: 'Total Pts', align: 'right',
              render: (v) => v > 0 ? v.toFixed(1) : '—',
            },
            {
              key: 'points_on_team', label: 'Pts on Roster', align: 'right',
              render: (v) => v > 0 ? v.toFixed(1) : '—',
            },
            {
              key: 'current_owner', label: 'Current Owner',
              render: (v) => v === 'Free Agent'
                ? <span style={{ color: 'var(--text-faint)', fontStyle: 'italic' }}>Free Agent</span>
                : v,
            },
          ]}
        />
      )}
    </div>
  )
}

// ─── Tab 2: Draft Board ───────────────────────────────────────────────────────

function DraftBoardTab() {
  const [season, setSeason] = useState(null)

  const { data: seasonsData, isLoading: loadingSeasons } = useQuery({
    queryKey: ['draft-seasons'],
    queryFn: () => fetch('/api/draft/seasons').then(r => r.json()),
  })

  const seasons = seasonsData?.seasons ?? []
  const activeSeason = season ?? seasons[0] ?? null

  const {
    data: boardData,
    isLoading: loadingBoard,
    error,
  } = useQuery({
    queryKey: ['draft-board', activeSeason],
    queryFn: () => fetch(`/api/draft/board/${activeSeason}`).then(r => r.json()),
    enabled: activeSeason !== null,
  })

  if (loadingSeasons) return <div className="text-gray-400">Loading seasons…</div>

  const picks = boardData?.picks ?? []

  // Group picks by round for the list display
  const byRound = {}
  picks.forEach(p => {
    if (!byRound[p.round]) byRound[p.round] = []
    byRound[p.round].push(p)
  })
  const rounds = Object.keys(byRound).map(Number).sort((a, b) => a - b)

  const draftLabel = boardData?.draft_type === 'linear' ? 'Linear' : 'Snake'

  return (
    <div>
      {/* Season selector */}
      <div className="flex flex-wrap gap-2 mb-6">
        {seasons.map(s => (
          <button
            key={s}
            onClick={() => setSeason(s)}
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              s === activeSeason
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {loadingBoard && <div className="text-gray-400">Loading draft…</div>}
      {error && <div className="text-red-400">Error loading draft board.</div>}

      {/* Position legend */}
      {!loadingBoard && boardData && (
        <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mb-4 text-xs text-gray-400">
            <span className="font-medium text-gray-300">
              {activeSeason} · {draftLabel} · {boardData.num_rounds} rounds · {boardData.num_teams} teams
            </span>
            {['QB', 'RB', 'WR', 'TE'].map(pos => (
              <span key={pos} className="flex items-center gap-1">
                <span className={`${POS_BADGE[pos]} text-white font-bold px-1.5 py-0.5 rounded text-xs`}>{pos}</span>
              </span>
            ))}
          </div>

          {/* Pick list grouped by round — no horizontal scrolling */}
          <div className="space-y-4">
            {rounds.map(round => (
              <div key={round}>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-1 px-1">
                  Round {round}
                </h3>
                <div className="rounded border border-gray-700 overflow-hidden">
                  {byRound[round].map((pick, i) => {
                    const { border, bg } = posStyle(pick.position)
                    return (
                      <div
                        key={i}
                        className={`flex items-center gap-3 px-3 py-2 border-l-4 ${border} ${bg} ${
                          i < byRound[round].length - 1 ? 'border-b border-gray-800/50' : ''
                        }`}
                      >
                        <span className="text-gray-500 text-xs w-8 shrink-0">#{pick.pick_no}</span>
                        <span className="text-gray-400 text-sm w-24 shrink-0 truncate">{pick.owner}</span>
                        <span className="text-white text-sm flex-1">{pick.player_name}</span>
                        <PosBadge pos={pick.position} />
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ─── Page root ───────────────────────────────────────────────────────────────

export default function Draft({ embedded = false }) {
  const [activeTab, setActiveTab] = useState('board')

  return (
    <div>
      {!embedded && <h1 className="text-2xl font-bold text-white mb-6">Draft History</h1>}
      <TabBar tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
      <TabPanel id="owner" activeTab={activeTab}><ByOwnerTab /></TabPanel>
      <TabPanel id="board" activeTab={activeTab}><DraftBoardTab /></TabPanel>
    </div>
  )
}
