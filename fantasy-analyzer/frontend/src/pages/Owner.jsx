/**
 * Owner.jsx — Owner Profile page.
 *
 * Tabs: Career Summary | Season Breakdown | H2H | Top Players | Trades | Waivers
 *
 * Pattern note: This page has a top-level owner selector. When the owner changes,
 * all queries re-fetch because the queryKey includes the owner name.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { TabBar, TabPanel } from '../components/Tabs'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'

const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

const TABS = [
  { id: 'summary',   label: 'Career Summary' },
  { id: 'seasons',   label: 'Seasons' },
  { id: 'h2h',       label: 'Head-to-Head' },
  { id: 'players',   label: 'Top Players' },
  { id: 'trades',    label: 'Trades' },
  { id: 'waivers',   label: 'Waivers' },
]

// ---------------------------------------------------------------------------
// Career summary metrics
// ---------------------------------------------------------------------------

function MetricCard({ label, value }) {
  return (
    <div className="bg-gray-800 rounded border border-gray-700 p-4">
      <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-xl font-bold text-white">{value ?? '—'}</p>
    </div>
  )
}

function CareerSummaryTab({ owner }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['owner-profile', owner],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(owner)}`).then(r => r.json()),
    enabled: !!owner,
  })

  if (isLoading) return <LoadingSpinner />
  if (error || data?.error) return <p className="text-red-400">{data?.error ?? error.message}</p>

  const c = data.career
  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">{owner} — Career Summary</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-6">
        <MetricCard label="Record"        value={c.record} />
        <MetricCard label="Win %"         value={pct(c.win_pct)} />
        <MetricCard label="Avg PPG"       value={c.avg_ppg} />
        <MetricCard label="Playoffs"      value={`${c.playoff_appearances}/${c.total_seasons}`} />
        <MetricCard label="Championships" value={c.championships} />
        <MetricCard label="Best Finish"   value={c.best_finish} />
        <MetricCard label="Total Trades"  value={c.total_trades} />
        <MetricCard label="Top Scorer"    value={c.top_scorer} />
      </div>

      <h3 className="text-base font-semibold mb-2 text-gray-300">Season-by-Season</h3>
      <DataTable
        rows={data.seasons ?? []}
        maxHeight="320px"
        columns={[
          { key: 'season',      label: 'Season' },
          { key: 'seed',        label: 'Seed',    align: 'right' },
          { key: 'record',      label: 'W-L' },
          { key: 'win_pct',     label: 'Win%',    align: 'right', render: v => pct(v) },
          { key: 'pts_for',     label: 'Pts For', align: 'right' },
          { key: 'pts_against', label: 'Pts Vs',  align: 'right' },
          { key: 'ppg',         label: 'PPG',     align: 'right' },
          { key: 'finish',      label: 'Finish' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Season breakdown table
// ---------------------------------------------------------------------------

function SeasonsTab({ owner }) {
  const { data, isLoading } = useQuery({
    queryKey: ['owner-profile', owner],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(owner)}`).then(r => r.json()),
    enabled: !!owner,
  })

  if (isLoading) return <LoadingSpinner />

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Season Breakdown</h2>
      <DataTable
        rows={data?.seasons ?? []}
        maxHeight="460px"
        columns={[
          { key: 'season',      label: 'Season' },
          { key: 'seed',        label: 'Seed',    align: 'right' },
          { key: 'record',      label: 'W-L' },
          { key: 'win_pct',     label: 'Win%',    align: 'right', render: v => pct(v) },
          { key: 'pts_for',     label: 'Pts For', align: 'right' },
          { key: 'pts_against', label: 'Pts Vs',  align: 'right' },
          { key: 'ppg',         label: 'PPG',     align: 'right' },
          { key: 'finish',      label: 'Finish' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// H2H vs all opponents
// ---------------------------------------------------------------------------

function H2HTab({ owner }) {
  const { data, isLoading } = useQuery({
    queryKey: ['owner-h2h', owner],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(owner)}/h2h`).then(r => r.json()),
    enabled: !!owner,
  })

  if (isLoading) return <LoadingSpinner />

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Head-to-Head vs Each Opponent</h2>
      <DataTable
        rows={data?.h2h ?? []}
        maxHeight="480px"
        columns={[
          { key: 'opponent',    label: 'Opponent' },
          { key: 'record',      label: 'W-L' },
          { key: 'win_pct',     label: 'Win%',     align: 'right', render: v => pct(v) },
          { key: 'avg_for',     label: 'Avg Scored', align: 'right' },
          { key: 'avg_against', label: 'Avg Allowed', align: 'right' },
          { key: 'games',       label: 'Games',    align: 'right' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Top scoring players
// ---------------------------------------------------------------------------

function TopPlayersTab({ owner }) {
  const [selectedSeason, setSelectedSeason] = useState(null)

  const { data: seasonsData } = useQuery({
    queryKey: ['history-seasons'],
    queryFn: () => fetch('/api/history/seasons').then(r => r.json()),
  })

  const seasons = seasonsData?.seasons ?? []

  const { data, isLoading } = useQuery({
    queryKey: ['owner-top-players', owner, selectedSeason],
    queryFn: () => {
      const url = selectedSeason
        ? `/api/owners/${encodeURIComponent(owner)}/top-players?season=${selectedSeason}`
        : `/api/owners/${encodeURIComponent(owner)}/top-players`
      return fetch(url).then(r => r.json())
    },
    enabled: !!owner,
  })

  if (isLoading) return <LoadingSpinner />

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-lg font-semibold">Top Scoring Players</h2>
        <select
          value={selectedSeason ?? ''}
          onChange={e => setSelectedSeason(e.target.value ? Number(e.target.value) : null)}
          className="ml-4 bg-gray-800 border border-gray-600 rounded px-3 py-1 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
        >
          <option value="">All Time</option>
          {seasons.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <p className="text-xs text-gray-500 mb-3">Regular season only · points scored while in the starting lineup</p>
      <DataTable
        rows={data?.players ?? []}
        maxHeight="490px"
        columns={[
          { key: 'player',        label: 'Player' },
          { key: 'position',      label: 'Pos' },
          { key: 'total_pts',     label: 'Total Pts',   align: 'right' },
          { key: 'weeks_started', label: 'Wks Started', align: 'right' },
          { key: 'avg_pts',       label: 'Avg/Wk',      align: 'right' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Trade history
// ---------------------------------------------------------------------------

function TradesTab({ owner }) {
  const { data, isLoading } = useQuery({
    queryKey: ['owner-trades', owner],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(owner)}/trades`).then(r => r.json()),
    enabled: !!owner,
  })

  if (isLoading) return <LoadingSpinner />

  const trades = data?.trades ?? []
  // Flatten into display rows
  const rows = trades.map(t => ({
    season: t.season,
    week: t.week,
    partners: t.partners.join(', ') || '—',
    received: t.received.join(', ') || '—',
    sent: t.sent.join(', ') || '—',
  }))

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Trade History</h2>
      <p className="text-sm text-gray-500 mb-3">{rows.length} trades</p>
      <DataTable
        rows={rows}
        maxHeight="500px"
        columns={[
          { key: 'season',   label: 'Season' },
          { key: 'week',     label: 'Week',   align: 'right' },
          { key: 'partners', label: 'Partner(s)' },
          { key: 'received', label: 'Received' },
          { key: 'sent',     label: 'Sent' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Waiver history
// ---------------------------------------------------------------------------

function WaiversTab({ owner }) {
  const { data, isLoading } = useQuery({
    queryKey: ['owner-waivers', owner],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(owner)}/waivers`).then(r => r.json()),
    enabled: !!owner,
  })

  if (isLoading) return <LoadingSpinner />

  const summary = data?.summary ?? {}
  const log = data?.log ?? []

  const rows = log.map(r => ({
    season: r.season,
    week: r.week,
    type: r.type,
    added: r.added ?? '—',
    dropped: r.dropped ?? '—',
    faab: r.faab_bid != null ? `$${r.faab_bid}` : '—',
  }))

  return (
    <div>
      {/* Summary metrics */}
      <div className="flex gap-4 mb-5">
        <div className="bg-gray-800 rounded border border-gray-700 px-4 py-3">
          <p className="text-xs text-gray-400">Waiver Claims</p>
          <p className="text-lg font-bold">{summary.waiver_claims ?? 0}</p>
        </div>
        <div className="bg-gray-800 rounded border border-gray-700 px-4 py-3">
          <p className="text-xs text-gray-400">FA Adds</p>
          <p className="text-lg font-bold">{summary.fa_adds ?? 0}</p>
        </div>
        <div className="bg-gray-800 rounded border border-gray-700 px-4 py-3">
          <p className="text-xs text-gray-400">FAAB Spent</p>
          <p className="text-lg font-bold">${summary.faab_spent ?? 0}</p>
        </div>
      </div>

      <DataTable
        rows={rows}
        maxHeight="500px"
        columns={[
          { key: 'season',  label: 'Season' },
          { key: 'week',    label: 'Week',  align: 'right' },
          { key: 'type',    label: 'Type' },
          { key: 'added',   label: 'Added' },
          { key: 'dropped', label: 'Dropped' },
          { key: 'faab',    label: 'FAAB Bid', align: 'right' },
        ]}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Owner page — owner selector + tabbed content
// ---------------------------------------------------------------------------

export default function Owner() {
  const [tab, setTab] = useState('summary')
  const [selectedOwner, setSelectedOwner] = useState(null)

  const { data: ownersData, isLoading } = useQuery({
    queryKey: ['owners-list'],
    queryFn: () => fetch('/api/owners/').then(r => r.json()),
  })

  const { data: avatarsData } = useQuery({
    queryKey: ['owner-avatars'],
    queryFn: () => fetch('/api/owners/avatars').then(r => r.json()),
    staleTime: Infinity,
  })

  const owners = ownersData?.owners ?? []
  const avatars = avatarsData?.avatars ?? {}
  const activeOwner = selectedOwner ?? owners[0]
  const avatarUrl = activeOwner ? avatars[activeOwner] : null

  if (isLoading) return <LoadingSpinner />

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Owner Profile</h1>

      {/* Owner selector */}
      <div className="flex items-center gap-3 mb-6">
        {avatarUrl && (
          <img
            src={avatarUrl}
            alt={activeOwner}
            className="w-10 h-10 rounded-full border-2 border-emerald-600 object-cover"
          />
        )}
        <label className="text-sm text-gray-400">Owner:</label>
        <select
          value={activeOwner ?? ''}
          onChange={e => { setSelectedOwner(e.target.value); setTab('summary') }}
          className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
        >
          {owners.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>

      <TabBar tabs={TABS} activeTab={tab} onChange={setTab} />

      <TabPanel id="summary" activeTab={tab}><CareerSummaryTab owner={activeOwner} /></TabPanel>
      <TabPanel id="seasons" activeTab={tab}><SeasonsTab     owner={activeOwner} /></TabPanel>
      <TabPanel id="h2h"     activeTab={tab}><H2HTab         owner={activeOwner} /></TabPanel>
      <TabPanel id="players" activeTab={tab}><TopPlayersTab  owner={activeOwner} /></TabPanel>
      <TabPanel id="trades"  activeTab={tab}><TradesTab      owner={activeOwner} /></TabPanel>
      <TabPanel id="waivers" activeTab={tab}><WaiversTab     owner={activeOwner} /></TabPanel>
    </div>
  )
}
