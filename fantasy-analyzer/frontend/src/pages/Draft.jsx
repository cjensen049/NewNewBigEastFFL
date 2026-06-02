/**
 * Draft.jsx — draft history page.
 *
 * Tab 1 "Draft Board": pick grid for one season.
 *   Columns = draft slots (each column belongs to one owner).
 *   Rows    = rounds (1 → max).
 *   Each cell shows the player picked at that slot/round, with a position badge.
 *
 * Tab 2 "By Owner": all picks for a selected owner across every season.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

// ─── Position badge colours ──────────────────────────────────────────────────

const POS_COLORS = {
  QB:  'bg-blue-600',
  RB:  'bg-green-700',
  WR:  'bg-purple-700',
  TE:  'bg-orange-600',
  K:   'bg-gray-500',
  DEF: 'bg-red-700',
}

function PosBadge({ pos }) {
  if (!pos) return null
  const color = POS_COLORS[pos] || 'bg-gray-600'
  return (
    <span className={`${color} text-white text-xs font-bold px-1 rounded ml-1`}>
      {pos}
    </span>
  )
}

// ─── Tabs ────────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'board', label: 'Draft Board' },
  { id: 'owner', label: 'By Owner' },
]

// ─── Tab 1: Draft Board ──────────────────────────────────────────────────────

function DraftBoardTab() {
  const [season, setSeason] = useState(null)

  // Fetch available seasons on mount
  const { data: seasonsData, isLoading: loadingSeasons } = useQuery({
    queryKey: ['draft-seasons'],
    queryFn: () => fetch('/api/draft/seasons').then(r => r.json()),
  })

  // Set default season once the list loads
  const seasons = seasonsData?.seasons ?? []
  const activeSeason = season ?? seasons[0] ?? null

  // Fetch the draft board for the selected season
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

  // Build the grid from the flat picks array.
  // grid[round][slot] = pick object.
  const picks = boardData?.picks ?? []
  const slotOwners = boardData?.slot_owners ?? {}  // {slot_number: owner_name}

  const slots = Object.keys(slotOwners).map(Number).sort((a, b) => a - b)
  const rounds = [...new Set(picks.map(p => p.round))].sort((a, b) => a - b)

  // Index picks by round + slot for O(1) lookup in the render loop
  const grid = {}
  picks.forEach(p => {
    if (!grid[p.round]) grid[p.round] = {}
    grid[p.round][p.draft_slot] = p
  })

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

      {!loadingBoard && boardData && (
        <>
          <p className="text-gray-400 text-sm mb-4">
            {activeSeason} · {draftLabel} draft · {boardData.num_rounds} rounds · {boardData.num_teams} teams
          </p>

          {/* Horizontally scrollable draft board — can be wide (12 owner columns) */}
          <div className="overflow-x-auto rounded border border-gray-700">
            <table className="text-sm border-collapse min-w-full">
              <thead>
                <tr className="bg-gray-800">
                  {/* Sticky round column */}
                  <th className="sticky left-0 z-10 bg-gray-800 px-3 py-2 text-left text-gray-400 font-medium border-r border-gray-700 whitespace-nowrap">
                    Round
                  </th>
                  {/* One column per draft slot, labelled with the owner's name */}
                  {slots.map(slot => (
                    <th
                      key={slot}
                      className="px-2 py-2 text-center text-gray-300 font-medium whitespace-nowrap border-r border-gray-700 min-w-[120px]"
                    >
                      <span className="text-xs text-gray-500 block">Slot {slot}</span>
                      {slotOwners[slot]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rounds.map((round, i) => (
                  <tr
                    key={round}
                    className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-850'}
                  >
                    {/* Sticky round number */}
                    <td className="sticky left-0 z-10 bg-inherit px-3 py-1.5 text-gray-400 font-medium border-r border-gray-700 whitespace-nowrap">
                      {round}
                    </td>
                    {slots.map(slot => {
                      const pick = grid[round]?.[slot]
                      return (
                        <td
                          key={slot}
                          className="px-2 py-1.5 border-r border-gray-800 text-gray-100 align-top"
                        >
                          {pick ? (
                            <span className="flex items-center gap-1 flex-wrap">
                              <span>{pick.player_name}</span>
                              <PosBadge pos={pick.position} />
                            </span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

// ─── Tab 2: By Owner ─────────────────────────────────────────────────────────

function ByOwnerTab() {
  const [selectedUserId, setSelectedUserId] = useState(null)

  // Fetch all owners who have picks (for the dropdown)
  const { data: ownersData, isLoading: loadingOwners } = useQuery({
    queryKey: ['draft-owners'],
    queryFn: () => fetch('/api/draft/owners').then(r => r.json()),
  })

  const owners = ownersData?.owners ?? []
  const activeUserId = selectedUserId ?? owners[0]?.user_id ?? null

  // Fetch picks for the selected owner
  const { data: picksData, isLoading: loadingPicks } = useQuery({
    queryKey: ['draft-owner-picks', activeUserId],
    queryFn: () => fetch(`/api/draft/owner/${activeUserId}`).then(r => r.json()),
    enabled: activeUserId !== null,
  })

  if (loadingOwners) return <div className="text-gray-400">Loading owners…</div>

  const activeOwner = owners.find(o => o.user_id === activeUserId)
  const allPicks = picksData?.picks ?? []

  // Group picks by season for display
  const bySeason = {}
  allPicks.forEach(p => {
    if (!bySeason[p.season]) bySeason[p.season] = []
    bySeason[p.season].push(p)
  })
  const seasonKeys = Object.keys(bySeason).map(Number).sort((a, b) => b - a)

  return (
    <div>
      {/* Owner selector */}
      <div className="flex items-center gap-3 mb-6">
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

      {loadingPicks && <div className="text-gray-400">Loading picks…</div>}

      {!loadingPicks && activeOwner && seasonKeys.length === 0 && (
        <div className="text-gray-500">No picks found for {activeOwner.owner}.</div>
      )}

      {/* One section per season */}
      {seasonKeys.map(season => {
        const picks = bySeason[season]
        const draftType = picks[0]?.draft_type || 'snake'
        return (
          <div key={season} className="mb-8">
            <h3 className="text-emerald-400 font-semibold text-base mb-2">
              {season} · {draftType === 'linear' ? 'Linear' : 'Snake'} draft
            </h3>
            <div className="overflow-x-auto rounded border border-gray-700">
              <table className="text-sm w-full">
                <thead>
                  <tr className="bg-gray-800 text-gray-400 text-left">
                    <th className="px-3 py-2 w-16">Round</th>
                    <th className="px-3 py-2 w-20">Pick #</th>
                    <th className="px-3 py-2">Player</th>
                    <th className="px-3 py-2 w-20">Position</th>
                  </tr>
                </thead>
                <tbody>
                  {picks.map((p, i) => (
                    <tr
                      key={i}
                      className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-800/50'}
                    >
                      <td className="px-3 py-1.5 text-gray-400">{p.round}</td>
                      <td className="px-3 py-1.5 text-gray-400">{p.pick_no}</td>
                      <td className="px-3 py-1.5 text-gray-100">{p.player_name}</td>
                      <td className="px-3 py-1.5">
                        <PosBadge pos={p.position} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ─── Page root ───────────────────────────────────────────────────────────────

export default function Draft() {
  const [activeTab, setActiveTab] = useState('board')

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Draft History</h1>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-gray-700">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium rounded-t transition-colors ${
              activeTab === tab.id
                ? 'bg-gray-700 text-white border-b-2 border-emerald-500'
                : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'board' && <DraftBoardTab />}
      {activeTab === 'owner' && <ByOwnerTab />}
    </div>
  )
}
