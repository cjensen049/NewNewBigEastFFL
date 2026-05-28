/**
 * History.jsx — REFERENCE PATTERN for all pages.
 *
 * This file shows the standard pattern:
 *   1. Import hooks, components, and chart primitives
 *   2. Break the page into small sub-components (one per tab section)
 *   3. Each sub-component fetches its own data with useQuery
 *   4. Handle loading and error states at the top of each component
 *   5. Render tables with <DataTable> and charts with Recharts
 *
 * Tabs: Standings | Season | Records | Weekly Scoring | Champions
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ResponsiveContainer,
} from 'recharts'

import { TabBar, TabPanel } from '../components/Tabs'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'

// ---------------------------------------------------------------------------
// Helper: format a win_pct decimal (0.634) → "63.4%"
// ---------------------------------------------------------------------------
const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

// ---------------------------------------------------------------------------
// Standings tab
// ---------------------------------------------------------------------------

function StandingsTab() {
  // useQuery fetches data from the API.
  // queryKey: a unique identifier — React Query re-fetches when this changes
  // queryFn: the function that actually calls the API
  const { data, isLoading, error } = useQuery({
    queryKey: ['history-standings'],
    queryFn: () => fetch('/api/history/standings').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />
  if (error) return <p className="text-red-400">Error: {error.message}</p>

  const rows = data.standings.map(s => ({
    ...s,
    win_pct_fmt: pct(s.win_pct),
    playoffs: `${s.playoff_appearances}/${s.seasons}`,
    titles: s.championships || '',
  }))

  // Data shaped for Recharts BarChart
  const chartData = data.standings.map(s => ({
    name: s.owner,
    'Win %': parseFloat((s.win_pct * 100).toFixed(1)),
    isChamp: s.championships > 0,
  }))

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">All-Time Standings</h2>
      <DataTable
        rows={rows}
        maxHeight="480px"
        columns={[
          { key: 'rank',         label: 'Rank',    align: 'right' },
          { key: 'owner',        label: 'Owner' },
          { key: 'seasons',      label: 'Seasons', align: 'right' },
          { key: 'record',       label: 'W-L' },
          { key: 'win_pct_fmt',  label: 'Win%',    align: 'right' },
          { key: 'total_pts',    label: 'Total Pts', align: 'right' },
          { key: 'ppg',          label: 'PPG',     align: 'right' },
          { key: 'playoffs',     label: 'Playoffs', align: 'right' },
          { key: 'titles',       label: 'Titles',  align: 'right' },
        ]}
      />

      <h2 className="text-lg font-semibold mt-8 mb-3">All-Time Win Percentage</h2>
      <p className="text-xs text-gray-500 mb-3">Gold bars = at least one championship</p>
      {/* ResponsiveContainer makes the chart fill its parent's width */}
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="name" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
          <YAxis
            stroke="#9CA3AF"
            domain={[0, 100]}
            tick={{ fontSize: 12 }}
            tickFormatter={v => `${v}%`}
          />
          <Tooltip
            formatter={(v) => [`${v}%`, 'Win %']}
            contentStyle={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              borderRadius: '6px',
            }}
          />
          {/* Cell lets us color each bar individually */}
          <Bar dataKey="Win %" label={{ position: 'top', fill: '#9CA3AF', fontSize: 10 }}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.isChamp ? '#FFD700' : '#4a90d9'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Season tab
// ---------------------------------------------------------------------------

function SeasonTab() {
  // First fetch the list of available seasons
  const { data: seasonsData, isLoading: loadingSeasons } = useQuery({
    queryKey: ['history-seasons'],
    queryFn: () => fetch('/api/history/seasons').then(r => r.json()),
  })

  // State: which season is selected (starts empty, set once seasons load)
  const [selectedSeason, setSelectedSeason] = useState(null)

  // When seasons load, default to the most recent
  const seasons = seasonsData?.seasons ?? []
  const activeSeason = selectedSeason ?? seasons[0]

  // Fetch the season breakdown — `enabled` prevents fetching before we have a year
  const { data: seasonData, isLoading: loadingSeason } = useQuery({
    queryKey: ['history-season', activeSeason],
    queryFn: () => fetch(`/api/history/season/${activeSeason}`).then(r => r.json()),
    enabled: !!activeSeason,
  })

  // Fetch the standings history grid
  const { data: histData } = useQuery({
    queryKey: ['history-standings-history'],
    queryFn: () => fetch('/api/history/standings-history').then(r => r.json()),
  })

  if (loadingSeasons) return <LoadingSpinner />

  const standings = seasonData?.standings ?? []
  const chartData = standings.map(s => ({
    name: s.owner,
    'Points For': s.pts_for,
    made_playoffs: s.made_playoffs,
  }))

  return (
    <div>
      {/* Season selector */}
      <div className="flex items-center gap-3 mb-6">
        <label className="text-sm text-gray-400">Season:</label>
        <select
          value={activeSeason ?? ''}
          onChange={e => setSelectedSeason(Number(e.target.value))}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
        >
          {seasons.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {loadingSeason ? (
        <LoadingSpinner />
      ) : (
        <>
          <h2 className="text-lg font-semibold mb-3">{activeSeason} Season Standings</h2>
          <DataTable
            rows={standings}
            maxHeight="460px"
            columns={[
              { key: 'seed',        label: 'Seed',    align: 'right' },
              { key: 'owner',       label: 'Owner' },
              { key: 'record',      label: 'W-L' },
              { key: 'win_pct',     label: 'Win%',    align: 'right', render: v => pct(v) },
              { key: 'pts_for',     label: 'Pts For', align: 'right' },
              { key: 'pts_against', label: 'Pts Vs',  align: 'right' },
              { key: 'ppg',         label: 'PPG',     align: 'right' },
              { key: 'finish',      label: 'Finish' },
            ]}
          />

          <h2 className="text-lg font-semibold mt-8 mb-3">Points Scored</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={[...chartData].sort((a, b) => b['Points For'] - a['Points For'])}
              margin={{ top: 20, right: 20, left: 0, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="name" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
              <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '6px' }}
              />
              <Bar dataKey="Points For">
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.made_playoffs ? '#4a90d9' : '#6b7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-gray-500 mt-1">Blue = made playoffs</p>
        </>
      )}

      {/* History grid — finish by season */}
      {histData && (
        <>
          <h2 className="text-lg font-semibold mt-10 mb-3">Owner Finish by Season</h2>
          <div className="overflow-x-auto rounded border border-gray-700">
            <table className="text-sm text-gray-300">
              <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                <tr>
                  <th className="px-3 py-2 sticky left-0 bg-gray-800">Owner</th>
                  {histData.seasons.map(s => (
                    <th key={s} className="px-3 py-2 text-right whitespace-nowrap">{s}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700/50">
                {histData.owner_grid.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-700/20">
                    <td className="px-3 py-2 sticky left-0 bg-gray-900 font-medium">{row.owner}</td>
                    {histData.seasons.map(s => (
                      <td key={s} className="px-3 py-2 text-right whitespace-nowrap text-gray-400">
                        {row[s] ?? '—'}
                      </td>
                    ))}
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

// ---------------------------------------------------------------------------
// Records tab
// ---------------------------------------------------------------------------

function RecordsTab() {
  const [includePlr, setIncludePlr] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['history-records', includePlr],
    queryFn: () =>
      fetch(`/api/history/records?include_playoffs=${includePlr}`).then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />
  if (error) return <p className="text-red-400">Error: {error.message}</p>

  return (
    <div>
      {/* Toggle between regular season and all games */}
      <div className="flex items-center gap-4 mb-5">
        {['Regular Season', 'All Games (incl. Playoffs)'].map((label, i) => {
          const active = i === 0 ? !includePlr : includePlr
          return (
            <button
              key={label}
              onClick={() => setIncludePlr(i === 1)}
              className={`px-4 py-1.5 text-sm rounded border transition-colors ${
                active
                  ? 'bg-emerald-700 border-emerald-600 text-white'
                  : 'border-gray-600 text-gray-400 hover:border-gray-500'
              }`}
            >
              {label}
            </button>
          )
        })}
      </div>

      <h2 className="text-lg font-semibold mb-3">League Records</h2>
      <DataTable
        rows={data.records}
        maxHeight="560px"
        columns={[
          { key: 'Category', label: 'Category' },
          { key: 'Holder',   label: 'Holder' },
          { key: 'Value',    label: 'Value',  align: 'right' },
          { key: 'Season',   label: 'Season', align: 'right' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Weekly Scoring tab
// ---------------------------------------------------------------------------

function WeeklyScoringTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['history-weekly-scoring'],
    queryFn: () => fetch('/api/history/weekly-scoring').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />
  if (error) return <p className="text-red-400">Error: {error.message}</p>

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div>
          <h2 className="text-lg font-semibold mb-3">Top 10 Single-Week Scores</h2>
          <DataTable
            rows={data.top}
            maxHeight="400px"
            columns={[
              { key: 'Rank',   label: 'Rank',   align: 'right' },
              { key: 'Owner',  label: 'Owner' },
              { key: 'Score',  label: 'Score',  align: 'right', render: v => v.toFixed(2) },
              { key: 'Season', label: 'Season', align: 'right' },
              { key: 'Week',   label: 'Week',   align: 'right' },
            ]}
          />
        </div>
        <div>
          <h2 className="text-lg font-semibold mb-3">Bottom 10 Single-Week Scores</h2>
          <DataTable
            rows={data.bottom}
            maxHeight="400px"
            columns={[
              { key: 'Rank',   label: 'Rank',   align: 'right' },
              { key: 'Owner',  label: 'Owner' },
              { key: 'Score',  label: 'Score',  align: 'right', render: v => v.toFixed(2) },
              { key: 'Season', label: 'Season', align: 'right' },
              { key: 'Week',   label: 'Week',   align: 'right' },
            ]}
          />
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-3">Weekly High / Low Score Counts</h2>
      <p className="text-sm text-gray-500 mb-3">Regular season only</p>
      <DataTable
        rows={data.counts}
        maxHeight="460px"
        columns={[
          { key: 'owner',      label: 'Owner' },
          { key: 'high_weeks', label: 'High Score Weeks', align: 'right' },
          { key: 'low_weeks',  label: 'Low Score Weeks',  align: 'right' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Playoff Records tab
// ---------------------------------------------------------------------------

function PlayoffRecordsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['h2h-playoff-records'],
    queryFn: () => fetch('/api/h2h/playoff-records').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">All-Time Playoff Records</h2>
      <DataTable
        rows={data?.records ?? []}
        maxHeight="480px"
        columns={[
          { key: 'owner',         label: 'Owner' },
          { key: 'appearances',   label: 'Appearances',  align: 'right' },
          { key: 'byes',          label: 'Byes',         align: 'right' },
          { key: 'record',        label: 'W-L' },
          { key: 'win_pct',       label: 'Win%',         align: 'right', render: v => pct(v) },
          { key: 'championships', label: 'Titles',       align: 'right' },
          { key: 'runner_up',     label: 'Runner-ups',   align: 'right' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Champions tab
// ---------------------------------------------------------------------------

const POS_ORDER = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPER_FLEX', 'K', 'DEF', 'BN']

function LineupTable({ starters }) {
  if (!starters || starters.length === 0) {
    return <p className="text-gray-500 text-sm italic">Lineup not available.</p>
  }
  const sorted = [...starters].sort(
    (a, b) => (POS_ORDER.indexOf(a.position) + 99) - (POS_ORDER.indexOf(b.position) + 99)
  )
  return (
    <DataTable
      rows={sorted.map(p => ({
        pos: p.position,
        player: p.player,
        pts: p.points != null ? p.points.toFixed(2) : '—',
      }))}
      maxHeight="340px"
      columns={[
        { key: 'pos',    label: 'Pos' },
        { key: 'player', label: 'Player' },
        { key: 'pts',    label: 'Pts', align: 'right' },
      ]}
    />
  )
}

function ChampionsTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['history-champions'],
    queryFn: () => fetch('/api/history/champions').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />
  if (error) return <p className="text-red-400">Error: {error.message}</p>

  return (
    <div className="space-y-6">
      {data.champions.map(cr => {
        const scoreStr =
          cr.champ_score && cr.ru_score
            ? `  (${cr.champ_score.toFixed(2)} – ${cr.ru_score.toFixed(2)})`
            : ''
        return (
          <div key={cr.season} className="rounded border border-gray-700 overflow-hidden">
            {/* Season header */}
            <div className="bg-gray-800 px-4 py-3 font-semibold text-amber-400">
              {cr.season} — {cr.champion}{scoreStr}
            </div>
            {/* Two-column lineup display */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4">
              <div>
                <p className="text-sm font-medium mb-2">🏆 {cr.champion}</p>
                <LineupTable starters={cr.champ_starters} />
              </div>
              <div>
                <p className="text-sm font-medium mb-2">🥈 {cr.runner_up}</p>
                <LineupTable starters={cr.ru_starters} />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// History page — assembles all tabs
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'standings', label: 'Standings' },
  { id: 'season',    label: 'Season View' },
  { id: 'records',   label: 'Records' },
  { id: 'weekly',    label: 'Weekly Scoring' },
  { id: 'playoff',   label: 'Playoff Records' },
  { id: 'champions', label: 'Champions' },
]

export default function History() {
  const [tab, setTab] = useState('standings')

  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">NNBE League History</h1>
      <p className="text-gray-400 text-sm mb-6">The New New Big East — 2021 through 2025</p>

      <TabBar tabs={TABS} activeTab={tab} onChange={setTab} />

      <TabPanel id="standings" activeTab={tab}><StandingsTab /></TabPanel>
      <TabPanel id="season"    activeTab={tab}><SeasonTab /></TabPanel>
      <TabPanel id="records"   activeTab={tab}><RecordsTab /></TabPanel>
      <TabPanel id="weekly"    activeTab={tab}><WeeklyScoringTab /></TabPanel>
      <TabPanel id="playoff"   activeTab={tab}><PlayoffRecordsTab /></TabPanel>
      <TabPanel id="champions" activeTab={tab}><ChampionsTab /></TabPanel>
    </div>
  )
}
