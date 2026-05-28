/**
 * HeadToHead.jsx — Head-to-Head, Rivalries, and Playoff Records page.
 *
 * Tabs: Matchup Lookup | Playoff Records | Rivalries | Full Matrix
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

import { TabBar, TabPanel } from '../components/Tabs'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'

const TABS = [
  { id: 'lookup',  label: 'Matchup Lookup' },
  { id: 'rivalry', label: 'Rivalries' },
  { id: 'matrix',  label: 'Full Matrix' },
]

// ---------------------------------------------------------------------------
// Matchup lookup
// ---------------------------------------------------------------------------

function MatchupLookupTab() {
  const { data: ownersData } = useQuery({
    queryKey: ['owners-list'],
    queryFn: () => fetch('/api/owners/').then(r => r.json()),
  })
  const owners = ownersData?.owners ?? []

  const [owner1, setOwner1] = useState(null)
  const [owner2, setOwner2] = useState(null)

  const o1 = owner1 ?? owners[0]
  const o2 = owner2 ?? owners[1]

  const { data, isLoading, error } = useQuery({
    queryKey: ['h2h-matchups', o1, o2],
    queryFn: () =>
      fetch(`/api/h2h/matchups?owner1=${encodeURIComponent(o1)}&owner2=${encodeURIComponent(o2)}`)
        .then(r => r.json()),
    enabled: !!o1 && !!o2 && o1 !== o2,
  })

  const matchups = data?.matchups ?? []

  // Shape matchup data for a line chart
  const chartData = matchups.map((m, i) => ({
    game: i + 1,
    label: `${m.season} Wk${m.week}`,
    [o1]: m.pts1,
    [o2]: m.pts2,
  }))

  const rows = matchups.map(m => ({
    season: m.season,
    week: m.week,
    pts1: m.pts1,
    pts2: m.pts2,
    winner: m.winner,
  }))

  return (
    <div>
      {/* Owner selectors */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Owner 1:</label>
          <select
            value={o1}
            onChange={e => setOwner1(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
          >
            {owners.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        <span className="text-gray-500 font-bold">vs</span>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Owner 2:</label>
          <select
            value={o2}
            onChange={e => setOwner2(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
          >
            {owners.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
      </div>

      {o1 === o2 && (
        <p className="text-yellow-400 text-sm">Select two different owners.</p>
      )}

      {isLoading && <LoadingSpinner />}

      {data && !isLoading && (
        <>
          {/* Summary metrics */}
          <div className="flex gap-4 mb-6">
            <div className="bg-gray-800 rounded border border-gray-700 px-4 py-3 text-center">
              <p className="text-xs text-gray-400 mb-1">{o1} Wins</p>
              <p className="text-2xl font-bold text-blue-400">{data.wins1}</p>
            </div>
            <div className="bg-gray-800 rounded border border-gray-700 px-4 py-3 text-center">
              <p className="text-xs text-gray-400 mb-1">Ties</p>
              <p className="text-2xl font-bold">{data.ties}</p>
            </div>
            <div className="bg-gray-800 rounded border border-gray-700 px-4 py-3 text-center">
              <p className="text-xs text-gray-400 mb-1">{o2} Wins</p>
              <p className="text-2xl font-bold text-red-400">{data.wins2}</p>
            </div>
          </div>

          {/* Line chart of scores each game */}
          <h2 className="text-lg font-semibold mb-3">Points Each Game</h2>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="label"
                stroke="#9CA3AF"
                tick={{ fontSize: 11, angle: -45, textAnchor: 'end' }}
                interval={0}
              />
              <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '6px' }}
              />
              <Legend verticalAlign="top" />
              <Line type="monotone" dataKey={o1} stroke="#4a90d9" dot strokeWidth={2} />
              <Line type="monotone" dataKey={o2} stroke="#e05a5a" dot strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>

          {/* Matchup log */}
          <h2 className="text-lg font-semibold mt-8 mb-3">All Matchups</h2>
          <DataTable
            rows={rows}
            maxHeight="420px"
            columns={[
              { key: 'season',  label: 'Season' },
              { key: 'week',    label: 'Week',  align: 'right' },
              { key: 'pts1',    label: `${o1} Pts`, align: 'right' },
              { key: 'pts2',    label: `${o2} Pts`, align: 'right' },
              { key: 'winner',  label: 'Winner' },
            ]}
          />
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Rivalries
// ---------------------------------------------------------------------------

function RivalriesTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['h2h-rivalries'],
    queryFn: () => fetch('/api/h2h/rivalries').then(r => r.json()),
  })

  const { data: nemesisData } = useQuery({
    queryKey: ['h2h-nemesis'],
    queryFn: () => fetch('/api/h2h/nemesis-prey').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />

  const rivalryRows = (data?.rivalries ?? []).map(r => ({
    matchup: `${r.owner_a} vs ${r.owner_b}`,
    record: `${r.a_wins}–${r.b_wins}`,
    games: r.total_games,
    leader: r.leader,
  }))

  const lopsidedRows = (data?.lopsided ?? []).map(r => ({
    matchup: `${r.owner_a} vs ${r.owner_b}`,
    record: `${r.a_wins}–${r.b_wins}`,
    games: r.total_games,
    leader: r.leader,
  }))

  const nemesisRows = (nemesisData?.nemesis_prey ?? []).map(r => ({
    owner: r.owner,
    nemesis: r.nemesis,
    vs_nemesis: r.nemesis_record,
    prey: r.prey,
    vs_prey: r.prey_record,
  }))

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h2 className="text-lg font-semibold mb-1">Top Rivalries</h2>
          <p className="text-xs text-gray-500 mb-3">Most games played with the closest records</p>
          <DataTable
            rows={rivalryRows}
            maxHeight="380px"
            columns={[
              { key: 'matchup', label: 'Matchup' },
              { key: 'record',  label: 'Record' },
              { key: 'games',   label: 'Games', align: 'right' },
              { key: 'leader',  label: 'Leader' },
            ]}
          />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-1">Most Lopsided</h2>
          <p className="text-xs text-gray-500 mb-3">Biggest mismatches (min 4 games)</p>
          <DataTable
            rows={lopsidedRows}
            maxHeight="380px"
            columns={[
              { key: 'matchup', label: 'Matchup' },
              { key: 'record',  label: 'Record' },
              { key: 'games',   label: 'Games', align: 'right' },
              { key: 'leader',  label: 'Dominant' },
            ]}
          />
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-1">Nemesis &amp; Prey</h2>
        <p className="text-xs text-gray-500 mb-3">Nemesis = worst record against (min 2 games) · Prey = best record against</p>
        <DataTable
          rows={nemesisRows}
          maxHeight="480px"
          columns={[
            { key: 'owner',      label: 'Owner' },
            { key: 'nemesis',    label: 'Nemesis' },
            { key: 'vs_nemesis', label: 'vs Nemesis' },
            { key: 'prey',       label: 'Prey' },
            { key: 'vs_prey',    label: 'vs Prey' },
          ]}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Full matrix
// ---------------------------------------------------------------------------

// Color a W-L cell string like "7-5" based on the win percentage
function cellColor(wl) {
  if (!wl || wl === '—') return ''
  const [w, l] = wl.split('-').map(Number)
  if (isNaN(w) || isNaN(l)) return ''
  const total = w + l
  if (total === 0) return ''
  const pct = w / total
  if (pct === 1.0) return 'bg-green-900 text-white font-bold'
  if (pct >= 0.70) return 'bg-green-800 text-white'
  if (pct >= 0.55) return 'bg-green-700/40'
  if (pct === 0.50) return 'bg-yellow-900/40'
  if (pct >= 0.35) return 'bg-red-800/40'
  if (pct > 0.0)   return 'bg-red-800 text-white'
  return 'bg-red-900 text-white font-bold'
}

function FullMatrixTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['h2h-matrix'],
    queryFn: () => fetch('/api/h2h/matrix').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />

  const owners = data?.owners ?? []
  const matrix = data?.matrix ?? {}

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">All-Time Regular Season Head-to-Head</h2>
      <p className="text-xs text-gray-500 mb-3">Read row vs column: row owner's record against column opponent</p>
      <div className="overflow-auto rounded border border-gray-700">
        <table className="text-xs text-gray-300">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              <th className="px-2 py-2 sticky left-0 bg-gray-800">Owner</th>
              {owners.map(o => (
                <th key={o} className="px-2 py-2 text-center whitespace-nowrap">{o}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {owners.map(row => (
              <tr key={row} className="hover:bg-gray-700/10">
                <td className="px-2 py-1.5 sticky left-0 bg-gray-900 font-medium whitespace-nowrap">{row}</td>
                {owners.map(col => {
                  const val = matrix[row]?.[col] ?? '—'
                  return (
                    <td key={col} className={`px-2 py-1.5 text-center whitespace-nowrap ${cellColor(val)}`}>
                      {val}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page assembly
// ---------------------------------------------------------------------------

export default function HeadToHead() {
  const [tab, setTab] = useState('lookup')

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Head-to-Head</h1>
      <TabBar tabs={TABS} activeTab={tab} onChange={setTab} />
      <TabPanel id="lookup"  activeTab={tab}><MatchupLookupTab /></TabPanel>
      <TabPanel id="rivalry" activeTab={tab}><RivalriesTab /></TabPanel>
      <TabPanel id="matrix"  activeTab={tab}><FullMatrixTab /></TabPanel>
    </div>
  )
}
