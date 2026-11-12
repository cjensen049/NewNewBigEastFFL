/**
 * PlayerProjectionTable.jsx — one owner's players vs. Sleeper's projections for a season.
 *
 * Shared by the owner dashboard's "Vs Projection" tab (with a Starters/Bench/All
 * switch) and the league Vs Projection page (starters only, with an owner picker).
 * One row per rostered player: games, projected, actual, season +/-, per game, then a
 * colored cell for each week. `mode` picks which weeks count: "starter", "bench"
 * or "all" (bench weeks are faded in "all").
 *
 * Weeks with no weekly Sleeper projection get a season-average stand-in (marked *) when
 * the player has a season-long projection, otherwise they show n/p and are left out
 * of +/-; the note under the table says which players that applies to.
 *
 * Also exports the position colors/badge and a small pill toggle used around the site.
 *
 * Props:
 *   owner  {string} — canonical owner name
 *   season {number}
 *   mode   {'starter'|'bench'|'all'}
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import DataTable from './DataTable'
import LoadingSpinner from './LoadingSpinner'
import { fmt1, signed, DiffText, WeekCell } from './DiffCells'

// Position colours — mirrors Draft.jsx
export const POS_STYLE = {
  QB: { border: 'border-l-red-500',    bg: 'bg-red-900/30' },
  RB: { border: 'border-l-green-500',  bg: 'bg-green-900/30' },
  WR: { border: 'border-l-blue-500',   bg: 'bg-blue-900/30' },
  TE: { border: 'border-l-orange-500', bg: 'bg-orange-900/30' },
}
const POS_BADGE = {
  QB: 'bg-red-700', RB: 'bg-green-700', WR: 'bg-blue-700', TE: 'bg-orange-600',
}
export function OwnerPosBadge({ pos }) {
  if (!pos) return null
  return (
    <span className={`${POS_BADGE[pos] ?? 'bg-gray-600'} text-white text-xs font-bold px-1.5 py-0.5 rounded`}>
      {pos}
    </span>
  )
}

// Row of pill buttons, same look as the source pills on Dynasty Rankings.
// options = [[value, label], ...]
export function PillToggle({ options, value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: '6px' }}>
      {options.map(([id, label]) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          style={{
            padding: '4px 12px', borderRadius: '5px', fontSize: '12px', fontWeight: 600, cursor: 'pointer',
            border: value === id ? '1px solid transparent' : '1px solid var(--border-mid)',
            background: value === id ? 'var(--brand-navy)' : 'var(--border)',
            color: value === id ? '#ffffff' : 'var(--text-muted)',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

const countWeeks = (obj) => Object.values(obj).filter(Boolean).length
const listPlayers = (items) => items.map(p => `${p.player} (${p.weeks} wk${p.weeks === 1 ? '' : 's'})`).join(', ')

export default function PlayerProjectionTable({ owner, season, mode }) {
  const { data, isLoading } = useQuery({
    queryKey: ['owner-player-projection', owner, season],
    queryFn: () => fetch(`/api/owners/${encodeURIComponent(owner)}/player-projection?season=${season}`).then(r => r.json()),
    enabled: !!owner && !!season,
  })

  const weeks = data?.weeks ?? []

  // One table row per player for the chosen mode; each week becomes a sortable w1, w2, ... column.
  const rows = useMemo(() => (data?.rows ?? []).flatMap(p => {
    const t = p.totals[mode]
    if (t.games === 0) return []
    const row = {
      player: p.player, position: p.position, games: t.games, projected: t.projected, actual: t.actual,
      diff: t.diff, avg_diff: t.avg_diff, _est: t.estimated_games > 0, _bench: {}, _np: {}, _estWeek: {},
    }
    for (const w of p.weeks) {
      if (mode === 'all' || w.role === mode) {
        row[`w${w.week}`] = w.diff
        row._bench[w.week] = w.role === 'bench'
        row._np[w.week] = w.projected == null      // no projection of any kind that week
        row._estWeek[w.week] = !!w.estimated       // season-average stand-in
      }
    }
    return [row]
  }), [data, mode])

  const totalDiff = rows.reduce((sum, r) => sum + (r.diff ?? 0), 0)
  const estimated = rows.map(r => ({ player: r.player, weeks: countWeeks(r._estWeek) })).filter(p => p.weeks > 0)
  const unprojected = rows.map(r => ({ player: r.player, weeks: countWeeks(r._np) })).filter(p => p.weeks > 0)

  const star = (row, node) => row._est ? <>{node}<span style={{ color: 'var(--text-faint)' }}>*</span></> : node

  const columns = [
    { key: 'player', label: 'Player' },
    { key: 'position', label: 'Pos', sortable: false, render: v => <OwnerPosBadge pos={v} /> },
    { key: 'games', label: 'G', align: 'right' },
    { key: 'projected', label: 'Proj', align: 'right', render: (v, row) => v == null ? '—' : star(row, fmt1(v)) },
    { key: 'actual', label: 'Actual', align: 'right', render: v => fmt1(v) },
    { key: 'diff', label: '+/-', align: 'right', render: (v, row) => star(row, <DiffText value={v} bold />) },
    { key: 'avg_diff', label: 'Per G', align: 'right', render: v => <DiffText value={v} /> },
    ...weeks.map(w => ({
      key: `w${w}`, label: `W${w}`, align: 'right',
      render: (v, row) => row._np[w]
        ? <span title="No Sleeper projection that week, so it's left out of +/-" style={{ fontSize: '11px', color: 'var(--text-faint)' }}>n/p</span>
        : <WeekCell value={v} dim={row._bench[w]} est={row._estWeek[w]} />,
    })),
  ]

  if (isLoading || !owner || !season) return <LoadingSpinner />
  if (rows.length === 0) {
    return <p className="text-gray-500">No {mode === 'all' ? '' : mode === 'starter' ? 'starter ' : 'bench '}games with projections for {owner} in {season}.</p>
  }

  return (
    <>
      <p className="text-xs text-gray-500 mb-2">
        {rows.length} players · {signed(totalDiff)} vs projection in total
        {mode === 'starter' && ' (this matches the team total on the league Vs Projection page)'}
      </p>
      {estimated.length > 0 && (
        <p className="text-xs mb-2" style={{ color: 'var(--text-faint)' }}>
          <strong style={{ color: 'var(--text-muted)' }}>* Estimated projection:</strong> {listPlayers(estimated)}.
          Sleeper has no weekly projection for these weeks (it drops players who have since retired or been released),
          so each uses that player's season-long per-game projection instead.
        </p>
      )}
      {unprojected.length > 0 && (
        <p className="text-xs mb-3" style={{ color: 'var(--text-faint)' }}>
          <strong style={{ color: 'var(--text-muted)' }}>n/p = no projection data:</strong> {listPlayers(unprojected)}.
          Not even a season-long projection exists, so those weeks are left out of +/- rather than guessed at.
        </p>
      )}
      <DataTable
        minWidth="900px"
        defaultSort="diff"
        defaultDir="desc"
        rows={rows}
        rowClassName={(p) => {
          const { border, bg } = POS_STYLE[p.position] ?? { border: 'border-l-gray-600', bg: 'bg-gray-800/40' }
          return `border-l-4 ${border} ${bg}`
        }}
        columns={columns}
        maxHeight="none"
      />
    </>
  )
}
