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

function rankCircleStyle(rank) {
  if (rank === 1) return { background: 'rgba(204,31,46,0.2)', color: 'var(--brand-red)' }
  if (rank === 2) return { background: 'rgba(26,58,107,0.3)', color: '#5b8dd9' }
  return { background: 'var(--border)', color: 'var(--text-muted)' }
}

function wlPillStyle(record) {
  if (!record) return {}
  const [w, l] = record.split('-').map(Number)
  if (w > l) return { background: 'rgba(63,185,80,0.12)', color: 'var(--green)' }
  if (l > w) return { background: 'rgba(204,31,46,0.1)',  color: 'var(--brand-red)' }
  return { background: 'rgba(227,179,65,0.12)', color: 'var(--gold)' }
}

function winPctColor(v) {
  if (v == null) return 'var(--text-faint)'
  const p = v * 100
  if (p < 40) return 'var(--brand-red)'
  if (p < 55) return 'var(--gold)'
  return 'var(--green)'
}

// ---------------------------------------------------------------------------
// Standings tab
// ---------------------------------------------------------------------------

function StandingsTab() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['history-standings'],
    queryFn: () => fetch('/api/history/standings').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />
  if (error) return <p className="text-red-400">Error: {error.message}</p>

  const chartData = data.standings.map(s => ({
    name: s.owner,
    'Win %': parseFloat((s.win_pct * 100).toFixed(1)),
    isChamp: s.championships > 0,
  }))

  return (
    <div>
      {/* Styled standings table */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', marginBottom: '32px' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>All-Time Standings</span>
        </div>
        <DataTable
          bordered={false}
          rowClassName={() => 'season-table-row'}
          rows={data.standings}
          defaultSort="rank"
          columns={[
            {
              key: 'rank', label: '#',
              render: (v) => (
                <div style={{ width: '20px', height: '20px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700, ...rankCircleStyle(v) }}>
                  {v}
                </div>
              ),
            },
            {
              key: 'owner', label: 'Owner',
              render: (v, s) => <span style={{ color: s.championships > 0 ? '#e3b341' : 'var(--text-primary)' }}>{v}</span>,
            },
            { key: 'seasons', label: 'Seasons', align: 'right' },
            {
              key: 'record', label: 'W-L', align: 'right',
              render: (v) => <span style={{ ...wlPillStyle(v), borderRadius: '4px', padding: '2px 8px', fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap' }}>{v}</span>,
            },
            {
              key: 'win_pct', label: 'Win%', align: 'right',
              render: (v) => <span style={{ fontWeight: 600, color: winPctColor(v) }}>{pct(v)}</span>,
            },
            {
              key: 'total_pts', label: 'Total Pts', align: 'right',
              render: (v) => v != null ? Number(v).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—',
            },
            { key: 'ppg', label: 'PPG', align: 'right' },
            {
              key: 'playoff_appearances', label: 'Playoffs', align: 'right',
              render: (v, s) => `${v}/${s.seasons}`,
            },
            {
              key: 'championships', label: 'Titles', align: 'right',
              render: (v) => <span style={{ fontWeight: 700, color: v > 0 ? '#e3b341' : 'var(--text-faint)' }}>{v > 0 ? '🏆'.repeat(Math.min(v, 4)) : '—'}</span>,
            },
          ]}
        />
      </div>

      {/* Win % bar chart */}
      <h2 className="fs-title" style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>All-Time Win Percentage</h2>
      <p style={{ fontSize: '11px', color: 'var(--text-faint)', marginBottom: '12px' }}>Gold bars = at least one championship</p>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 20, right: 20, left: 0, bottom: 5 }} style={{ background: 'transparent' }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2d47" />
          <XAxis dataKey="name" tick={{ fill: '#4a6380', fontSize: 12 }} axisLine={{ stroke: '#1e2d47' }} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: '#4a6380', fontSize: 12 }} tickFormatter={v => `${v}%`} axisLine={false} tickLine={false} />
          <Tooltip
            formatter={(v) => [`${v}%`, 'Win %']}
            contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '6px' }}
            labelStyle={{ color: 'var(--text-primary)' }}
            itemStyle={{ color: 'var(--text-muted)' }}
          />
          <Bar dataKey="Win %" label={{ position: 'top', fill: '#4a6380', fontSize: 10 }}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.isChamp ? '#e3b341' : '#1a3a6b'} />
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
          <h2 className="text-base md:text-lg font-semibold mb-3">{activeSeason} Season Standings</h2>
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

          <h2 className="text-base md:text-lg font-semibold mt-8 mb-3">Points Scored</h2>
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
          <h2 className="text-base md:text-lg font-semibold mt-10 mb-3">Owner Finish by Season</h2>
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

      <h2 className="text-base md:text-lg font-semibold mb-3">League Records</h2>
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
          <h2 className="text-base md:text-lg font-semibold mb-3">Top 10 Single-Week Scores</h2>
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
          <h2 className="text-base md:text-lg font-semibold mb-3">Bottom 10 Single-Week Scores</h2>
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

      <h2 className="text-base md:text-lg font-semibold mb-3">Weekly High / Low Score Counts</h2>
      <p className="text-xs md:text-sm text-gray-500 mb-3">Regular season only</p>
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
      <h2 className="text-base md:text-lg font-semibold mb-3">All-Time Playoff Records</h2>
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

export default function History({ embedded = false }) {
  const [tab, setTab] = useState('standings')

  return (
    <div>
      {!embedded && (
        <>
          <h1 className="text-2xl font-bold mb-1">NNBE League History</h1>
          <p className="text-gray-400 text-sm mb-6">The New New Big East — 2021 through 2025</p>
        </>
      )}

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
