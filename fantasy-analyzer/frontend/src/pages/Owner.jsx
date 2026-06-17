/**
 * Owner.jsx — Owner Profile page.
 *
 * Full-width header: owner selector, identity row (avatar + name + membership),
 * and inline tab bar. Tab content is constrained to max-width container.
 *
 * Tabs: Career Summary | Head-to-Head | Top Players | Draft Picks | Trades | Waivers
 */
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { TabPanel } from '../components/Tabs'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'

const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'
const fmtPts = (v) => v != null ? Number(v).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—'

const TABS = [
  { id: 'summary', label: 'Career Summary' },
  { id: 'h2h',     label: 'Head-to-Head' },
  { id: 'players', label: 'Top Players' },
  { id: 'draft',   label: 'Draft Picks' },
  { id: 'trades',  label: 'Trades' },
  { id: 'waivers', label: 'Waivers' },
]

const CONTAINER = { maxWidth: '1280px', margin: '0 auto', padding: '0 clamp(12px, 3vw, 24px)' }

// Position colours — mirrors Draft.jsx
const POS_STYLE = {
  QB: { border: 'border-l-red-500',    bg: 'bg-red-900/30' },
  RB: { border: 'border-l-green-500',  bg: 'bg-green-900/30' },
  WR: { border: 'border-l-blue-500',   bg: 'bg-blue-900/30' },
  TE: { border: 'border-l-orange-500', bg: 'bg-orange-900/30' },
}
const POS_BADGE = {
  QB: 'bg-red-700', RB: 'bg-green-700', WR: 'bg-blue-700', TE: 'bg-orange-600',
}
function OwnerPosBadge({ pos }) {
  if (!pos) return null
  return (
    <span className={`${POS_BADGE[pos] ?? 'bg-gray-600'} text-white text-xs font-bold px-1.5 py-0.5 rounded`}>
      {pos}
    </span>
  )
}

// ─── Career Summary helpers ───────────────────────────────────────────────────

function statColor(label, rawValue) {
  const v = parseFloat(rawValue)
  if (label === 'Win %') {
    if (v < 40) return 'var(--brand-red)'
    if (v < 55) return 'var(--gold)'
    return 'var(--green)'
  }
  if (label === 'Championships') {
    return v === 0 ? 'var(--brand-red)' : 'var(--green)'
  }
  if (label === 'Avg PPG') {
    if (v > 130) return 'var(--green)'
    if (v > 110) return 'var(--gold)'
    return 'var(--text-primary)'
  }
  return 'var(--text-primary)'
}

function wlPillStyle(record) {
  if (!record) return {}
  const parts = record.split('-').map(Number)
  const [w, l] = parts
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

function finishColor(finish) {
  if (!finish || finish === '—') return 'var(--text-faint)'
  const n = parseInt(finish)
  if (n === 1 || String(finish).toLowerCase().includes('champ')) return 'var(--gold)'
  if (n <= 3) return 'var(--gold)'
  return 'var(--text-faint)'
}

function StatCard({ label, value, subLabel }) {
  const isTopScorer = label === 'Top Scorer'
  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', padding: '14px 16px' }}>
      <p style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '6px' }}>{label}</p>
      <p style={{
        fontFamily: isTopScorer ? 'var(--font-body)' : 'var(--font-display)',
        fontSize: isTopScorer ? '16px' : '32px',
        lineHeight: 1,
        color: isTopScorer ? '#5b8dd9' : statColor(label, value),
      }}>
        {value ?? '—'}
      </p>
      {subLabel && <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>{subLabel}</p>}
    </div>
  )
}

// ─── Career Summary tab ───────────────────────────────────────────────────────

function CareerSummaryTab({ owner }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['owner-profile', owner],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(owner)}`).then(r => r.json()),
    enabled: !!owner,
  })

  const { data: rivalData } = useQuery({
    queryKey: ['h2h-nemesis-prey'],
    queryFn: () => fetch('/api/h2h/nemesis-prey').then(r => r.json()),
    staleTime: Infinity,
  })

  if (isLoading) return <LoadingSpinner />
  if (error || data?.error) return <p style={{ color: 'var(--brand-red)' }}>{data?.error ?? error.message}</p>

  const c = data.career
  const rival = rivalData?.nemesis_prey?.find(r => r.owner === owner)

  // Sort seasons newest-first for display
  const seasons = [...(data.seasons ?? [])].sort((a, b) => b.season - a.season)

  return (
    <div>
      {/* Row 1 stat cards */}
      <div className="stat-cards-grid" style={{ marginBottom: '10px' }}>
        <StatCard label="Record"   value={c.record} />
        <StatCard label="Win %"    value={c.win_pct != null ? `${(c.win_pct * 100).toFixed(1)}` : '—'} />
        <StatCard label="Avg PPG"  value={c.avg_ppg} />
        <StatCard label="Playoffs" value={`${c.playoff_appearances}/${c.total_seasons}`} />
      </div>

      {/* Row 2 stat cards */}
      <div className="stat-cards-grid" style={{ marginBottom: '20px' }}>
        <StatCard label="Championships" value={c.championships} />
        <StatCard label="Best Finish"   value={c.best_finish} />
        <StatCard label="Total Trades"  value={c.total_trades} />
        <StatCard label="Top Scorer"    value={c.top_scorer} />
      </div>

      {/* Nemesis / Prey row */}
      <div className="nemesis-prey-grid">
        <div style={{ background: 'rgba(204,31,46,0.08)', border: '1px solid rgba(204,31,46,0.25)', borderRadius: '10px', padding: '16px' }}>
          <p style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--brand-red)', marginBottom: '6px' }}>☠ Nemesis</p>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '26px', color: 'var(--text-primary)', lineHeight: 1, marginBottom: '4px' }}>
            {rival?.nemesis ?? '—'}
          </p>
          {rival?.nemesis_record && <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{rival.nemesis_record}</p>}
        </div>
        <div style={{ background: 'rgba(63,185,80,0.06)', border: '1px solid rgba(63,185,80,0.2)', borderRadius: '10px', padding: '16px' }}>
          <p style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--green)', marginBottom: '6px' }}>🎯 Prey</p>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '26px', color: 'var(--text-primary)', lineHeight: 1, marginBottom: '4px' }}>
            {rival?.prey ?? '—'}
          </p>
          {rival?.prey_record && <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{rival.prey_record}</p>}
        </div>
      </div>

      {/* Season-by-season table */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Season by Season</span>
          <span style={{ background: 'rgba(26,58,107,0.3)', color: '#5b8dd9', border: '1px solid rgba(91,141,217,0.2)', borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 600 }}>
            {seasons.length} seasons
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-page)' }}>
                {['Season', 'Seed', 'W-L', 'Win%', 'Pts For', 'Pts Vs', 'PPG', 'Finish'].map((col, i) => (
                  <th key={col} style={{
                    padding: '8px 12px',
                    fontSize: '11px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase',
                    color: 'var(--text-faint)', textAlign: i === 0 ? 'left' : 'right',
                    whiteSpace: 'nowrap',
                  }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {seasons.map((s, i) => {
                const prevPpg = seasons[i + 1]?.ppg
                const currPpg = s.ppg
                const trend = prevPpg != null && currPpg != null
                  ? currPpg > prevPpg ? '↑' : currPpg < prevPpg ? '↓' : null
                  : null
                const trendColor = trend === '↑' ? 'var(--green)' : 'var(--brand-red)'

                const pillStyle = { ...wlPillStyle(s.record), borderRadius: '4px', padding: '2px 8px', fontSize: '13px', fontWeight: 600 }

                return (
                  <tr key={s.season} className="season-table-row" style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '9px 12px', fontSize: '16px', fontWeight: 500, color: 'var(--text-primary)' }}>{s.season}</td>
                    <td style={{ padding: '9px 12px', fontSize: '16px', color: 'var(--text-muted)', textAlign: 'right' }}>{s.seed ?? '—'}</td>
                    <td style={{ padding: '9px 12px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <span style={{ ...pillStyle, whiteSpace: 'nowrap' }}>{s.record ?? '—'}</span>
                    </td>
                    <td style={{ padding: '9px 12px', textAlign: 'right', fontSize: '16px', fontWeight: 600, color: winPctColor(s.win_pct) }}>
                      {pct(s.win_pct)}
                    </td>
                    <td style={{ padding: '9px 12px', textAlign: 'right', fontSize: '16px', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                      {fmtPts(s.pts_for)}
                    </td>
                    <td style={{ padding: '9px 12px', textAlign: 'right', fontSize: '16px', color: 'var(--text-faint)', fontVariantNumeric: 'tabular-nums' }}>
                      {fmtPts(s.pts_against)}
                    </td>
                    <td style={{ padding: '9px 12px', textAlign: 'right', fontSize: '16px', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                      {s.ppg ?? '—'}
                      {trend && <span style={{ color: trendColor, marginLeft: '3px', fontSize: '11px' }}>{trend}</span>}
                    </td>
                    <td style={{ padding: '9px 12px', textAlign: 'right', fontSize: '16px', fontWeight: 600, color: finishColor(s.finish) }}>
                      {s.finish ?? '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ─── H2H tab ──────────────────────────────────────────────────────────────────

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
          { key: 'win_pct',     label: 'Win%',       align: 'right', render: v => pct(v) },
          { key: 'avg_for',     label: 'Avg Scored',  align: 'right' },
          { key: 'avg_against', label: 'Avg Allowed', align: 'right' },
          { key: 'games',       label: 'Games',       align: 'right' },
        ]}
      />
    </div>
  )
}

// ─── Top Players tab ──────────────────────────────────────────────────────────

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

// ─── Draft Picks tab ──────────────────────────────────────────────────────────

function DraftPicksTab({ owner }) {
  const [sortMode, setSortMode] = useState('pts')

  const { data: draftOwnersData } = useQuery({
    queryKey: ['draft-owners'],
    queryFn: () => fetch('/api/draft/owners').then(r => r.json()),
    staleTime: Infinity,
  })

  const userId = draftOwnersData?.owners?.find(o => o.owner === owner)?.user_id

  const { data, isLoading } = useQuery({
    queryKey: ['draft-owner-picks', userId],
    queryFn: () => fetch(`/api/draft/owner/${userId}`).then(r => r.json()),
    enabled: !!userId,
  })

  if (isLoading || !draftOwnersData) return <LoadingSpinner />
  if (!userId) return <p className="text-gray-500">No draft data found for {owner}.</p>

  const allPicks = data?.picks ?? []

  const sorted = [...allPicks].sort((a, b) =>
    sortMode === 'pts'
      ? b.points_on_team - a.points_on_team
      : (b.season - a.season) || (a.round - b.round) || (a.pick_no - b.pick_no)
  )

  const totalPts = allPicks.reduce((s, p) => s + (p.points_on_team ?? 0), 0)

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <h2 className="text-lg font-semibold">Draft Picks</h2>
        <p className="text-xs text-gray-500">Points scored while on {owner}'s roster only</p>
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-gray-400 text-sm">Sort</label>
          <div className="flex rounded overflow-hidden border border-gray-600">
            {[['pts', 'By Points'], ['draft', 'By Draft']].map(([mode, label]) => (
              <button
                key={mode}
                onClick={() => setSortMode(mode)}
                className={`px-3 py-1 text-xs font-medium transition-colors ${
                  sortMode === mode ? 'bg-emerald-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {allPicks.length > 0 && (
        <p className="text-xs text-gray-500 mb-3">
          {allPicks.length} career picks · {totalPts.toFixed(1)} total pts on roster
        </p>
      )}

      <div className="rounded border border-gray-700 overflow-hidden overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: '640px' }}>
          <thead>
            <tr className="bg-gray-800 text-gray-400 text-left text-xs uppercase tracking-wide">
              <th className="px-3 py-2">Player</th>
              <th className="px-3 py-2 w-12">Pos</th>
              <th className="px-3 py-2 w-16">Season</th>
              <th className="px-3 py-2 w-14 text-center">Rd</th>
              <th className="px-3 py-2 w-16 text-center">Pick</th>
              <th className="px-3 py-2 w-28 text-right">Total Pts</th>
              <th className="px-3 py-2 w-28 text-right">Pts on Roster</th>
              <th className="px-3 py-2 w-24">Current Owner</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p, i) => {
              const { border, bg } = POS_STYLE[p.position] ?? { border: 'border-l-gray-600', bg: 'bg-gray-800/40' }
              return (
                <tr key={i} className={`border-l-4 ${border} ${bg} border-b border-gray-800/50`}>
                  <td className="px-3 py-2 text-white font-medium">{p.player_name}</td>
                  <td className="px-3 py-2"><OwnerPosBadge pos={p.position} /></td>
                  <td className="px-3 py-2 text-gray-400">{p.season}</td>
                  <td className="px-3 py-2 text-gray-400 text-center">{p.round}</td>
                  <td className="px-3 py-2 text-gray-400 text-center">{p.pick_no}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">
                    {p.total_points > 0 ? p.total_points.toFixed(1) : '—'}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono font-medium ${
                    p.points_on_team > 500 ? 'text-emerald-400' :
                    p.points_on_team > 200 ? 'text-emerald-600' :
                    p.points_on_team > 0   ? 'text-gray-300'    : 'text-gray-600'
                  }`}>
                    {p.points_on_team > 0 ? p.points_on_team.toFixed(1) : '—'}
                  </td>
                  <td className="px-3 py-2 text-sm">
                    {p.current_owner === 'Free Agent'
                      ? <span className="text-gray-500 italic">Free Agent</span>
                      : <span className="text-gray-300">{p.current_owner}</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Trades tab ───────────────────────────────────────────────────────────────

function TradesTab({ owner }) {
  const { data, isLoading } = useQuery({
    queryKey: ['owner-trades', owner],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(owner)}/trades`).then(r => r.json()),
    enabled: !!owner,
  })

  if (isLoading) return <LoadingSpinner />

  const trades = data?.trades ?? []
  const rows = trades.map(t => ({
    season:   t.season,
    week:     t.week,
    partners: t.partners.join(', ') || '—',
    received: t.received.join(', ') || '—',
    sent:     t.sent.join(', ') || '—',
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

// ─── Waivers tab ──────────────────────────────────────────────────────────────

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
    season:  r.season,
    week:    r.week,
    type:    r.type,
    added:   r.added ?? '—',
    dropped: r.dropped ?? '—',
    faab:    r.faab_bid != null ? `$${r.faab_bid}` : '—',
  }))

  return (
    <div>
      <div className="flex gap-4 mb-5">
        <div className="bg-gray-800 rounded border border-gray-700 px-4 py-3">
          <p className="text-xs text-gray-400">Waiver Claims</p>
          <p className="text-lg font-bold">{summary.waiver_claims ?? 0}</p>
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
          { key: 'week',    label: 'Week',    align: 'right' },
          { key: 'type',    label: 'Type' },
          { key: 'added',   label: 'Added' },
          { key: 'dropped', label: 'Dropped' },
          { key: 'faab',    label: 'FAAB Bid', align: 'right' },
        ]}
      />
    </div>
  )
}

// ─── Page root ────────────────────────────────────────────────────────────────

function initials(name) {
  if (!name) return '?'
  return name.split(' ').map(w => w[0] ?? '').join('').slice(0, 2).toUpperCase()
}

export default function Owner() {
  const { name: urlName } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState('summary')

  const { data: ownersData, isLoading } = useQuery({
    queryKey: ['owners-list'],
    queryFn: () => fetch('/api/owners/').then(r => r.json()),
  })

  const owners = ownersData?.owners ?? []
  const activeOwner = urlName ?? owners[0]

  const { data: profileData } = useQuery({
    queryKey: ['owner-profile-meta', activeOwner],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(activeOwner)}`).then(r => r.json()),
    enabled: !!activeOwner,
  })

  const { data: avatarsData } = useQuery({
    queryKey: ['owner-avatars'],
    queryFn: () => fetch('/api/owners/avatars').then(r => r.json()),
    staleTime: Infinity,
  })

  if (isLoading) return <LoadingSpinner />

  const seasons = profileData?.seasons ?? []
  const memberSince = profileData?.joined_season ?? (seasons.length > 0 ? Math.min(...seasons.map(s => s.season)) : null)
  const departedAfter = profileData?.departed_after ?? null

  return (
    <div>
      {/* Full-width header */}
      <div style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
        <div style={{ ...CONTAINER, padding: '20px clamp(12px, 3vw, 24px) 0' }}>

          {/* Owner selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Owner</span>
            <select
              value={activeOwner ?? ''}
              onChange={e => { navigate(`/owner/${encodeURIComponent(e.target.value)}`); setTab('summary') }}
              style={{ background: 'var(--border)', border: '1px solid var(--border-mid)', color: 'var(--text-primary)', borderRadius: '6px', padding: '5px 10px', fontSize: '13px', fontFamily: 'var(--font-body)' }}
            >
              {owners.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Identity row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            {/* Avatar — Sleeper profile pic if available, initials fallback */}
            {avatarsData?.avatars?.[activeOwner] ? (
              <img
                src={avatarsData.avatars[activeOwner]}
                alt={activeOwner}
                style={{
                  width: '48px', height: '48px', borderRadius: '50%',
                  border: '2px solid var(--border-mid)',
                  objectFit: 'cover', flexShrink: 0,
                }}
              />
            ) : (
              <div style={{
                width: '48px', height: '48px', borderRadius: '50%',
                border: '2px solid var(--border-mid)',
                background: 'linear-gradient(135deg, var(--brand-navy), var(--brand-red))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                <span style={{ fontFamily: 'var(--font-display)', fontSize: '20px', color: '#fff', lineHeight: 1 }}>
                  {initials(activeOwner)}
                </span>
              </div>
            )}

            {/* Name + info */}
            <div>
              <p style={{ fontFamily: 'var(--font-display)', fontSize: '32px', letterSpacing: '2px', lineHeight: 1, color: 'var(--text-primary)', margin: 0 }}>
                {activeOwner}
              </p>
              <p style={{ fontSize: '12px', color: 'var(--text-faint)', marginTop: '4px' }}>
                {memberSince ? `Member since ${memberSince}` : ''}
                {memberSince && seasons.length ? ` · ${seasons.length} season${seasons.length !== 1 ? 's' : ''}` : ''}
                {departedAfter ? (
                  <span style={{ marginLeft: '8px', background: 'rgba(204,31,46,0.12)', color: 'var(--brand-red)', border: '1px solid rgba(204,31,46,0.25)', borderRadius: '4px', padding: '1px 7px', fontSize: '11px', fontWeight: 600 }}>
                    Departed after {departedAfter}
                  </span>
                ) : null}
              </p>
            </div>
          </div>

          {/* Tab bar — desktop: flush to bottom of header */}
          <div className="hidden md:flex" style={{ gap: '0', marginBottom: '-1px', overflowX: 'auto' }}>
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`owner-tab${tab === t.id ? ' active' : ''}`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab bar — mobile: pill scroller */}
          <div className="league-mobile-pills md:hidden" style={{ padding: '10px 0 8px' }}>
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  display: 'inline-block',
                  padding: '6px 16px',
                  borderRadius: '20px',
                  fontSize: '13px',
                  fontWeight: 500,
                  marginRight: '8px',
                  cursor: 'pointer',
                  border: tab === t.id ? 'none' : '1px solid var(--border)',
                  background: tab === t.id ? 'var(--brand-red)' : 'var(--bg-surface)',
                  color: tab === t.id ? '#ffffff' : 'var(--text-muted)',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

        </div>
      </div>

      {/* Tab content */}
      <div style={{ ...CONTAINER, padding: '24px clamp(12px, 3vw, 24px)' }}>
        <TabPanel id="summary" activeTab={tab}><CareerSummaryTab owner={activeOwner} /></TabPanel>
        <TabPanel id="h2h"     activeTab={tab}><H2HTab           owner={activeOwner} /></TabPanel>
        <TabPanel id="players" activeTab={tab}><TopPlayersTab    owner={activeOwner} /></TabPanel>
        <TabPanel id="draft"   activeTab={tab}><DraftPicksTab    owner={activeOwner} /></TabPanel>
        <TabPanel id="trades"  activeTab={tab}><TradesTab        owner={activeOwner} /></TabPanel>
        <TabPanel id="waivers" activeTab={tab}><WaiversTab       owner={activeOwner} /></TabPanel>
      </div>
    </div>
  )
}
