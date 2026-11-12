/**
 * VsProjection.jsx — how each owner's starters performed vs. Sleeper's projections.
 * Its own tab under League (between Power Rankings and History).
 *
 * One row per owner. "Players vs projection" columns show the actual points
 * their starters scored minus the sum of those starters' own Sleeper
 * projections (+20 = starters beat projection by 20), per week (W1, W2, ...),
 * for the season, per week on average, and over the last 3 weeks. "vs League"
 * is the season total after subtracting each week's league-wide average, which
 * removes seasons where Sleeper's projections ran high or low for everyone. This
 * is about the players, not the manager's choices.
 *
 * "Lineup decisions" columns (Efficiency, Left on Bench) are a separate
 * measure of the manager's start/sit: actual score as a % of the best lineup
 * in hindsight, and the points left on the bench.
 *
 * Data: /api/in-season/projection-performance/{season}. Click any header to sort.
 */
import { useState, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import DataTable from '../components/DataTable'
import PlayerProjectionTable from '../components/PlayerProjectionTable'
import LoadingSpinner from '../components/LoadingSpinner'
import { fmt1, signed, DiffText, WeekCell } from '../components/DiffCells'

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function VsProjection() {
  const { data: seasonsData, isLoading: loadSeasons } = useQuery({
    queryKey: ['inseason-seasons'],
    queryFn: () => fetch('/api/in-season/seasons').then(r => r.json()),
  })
  const [selectedSeason, setSelectedSeason] = useState(null)
  const seasons = seasonsData?.seasons ?? []
  const season = selectedSeason ?? seasons[0]

  const { data, isLoading } = useQuery({
    queryKey: ['projection-performance', season],
    queryFn: () => fetch(`/api/in-season/projection-performance/${season}`).then(r => r.json()),
    enabled: !!season,
  })

  const weeks = data?.weeks ?? []

  // Player detail below the table: which owner's players to list (defaults to the table's leader)
  const [detailOwner, setDetailOwner] = useState(null)
  const detailRef = useRef(null)
  const ownerNames = (data?.rows ?? []).map(r => r.owner)
  const activeDetailOwner = ownerNames.includes(detailOwner) ? detailOwner : ownerNames[0]
  const showOwner = name => {
    setDetailOwner(name)
    detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // Flatten each owner's weekly list into w1, w2, ... keys so every week is a sortable column.
  const rows = useMemo(() => (data?.rows ?? []).map(r => {
    const flat = { ...r }
    for (const w of r.weeks) flat[`w${w.week}`] = w.diff
    return flat
  }), [data])

  // Highlight the best and worst efficiency rather than judging against an arbitrary cutoff.
  const effs = rows.map(r => r.efficiency_pct).filter(v => v != null)
  const bestEff = Math.max(...effs)
  const worstEff = Math.min(...effs)

  const columns = [
    {
      key: 'owner', label: 'Owner',
      render: v => (
        <button onClick={() => showOwner(v)} title="Show this owner's players below"
          style={{ fontWeight: 600, background: 'none', border: 'none', padding: 0, color: 'var(--text-primary)', cursor: 'pointer', textDecoration: 'underline dotted', textUnderlineOffset: '3px' }}>
          {v}
        </button>
      ),
    },
    {
      key: 'total_diff', label: 'Season +/-', align: 'right',
      render: (v, row) => <><DiffText value={v} bold />{row.estimated_n > 0 && <span title="Includes a season-average stand-in projection for a player Sleeper no longer lists" style={{ color: 'var(--text-faint)' }}>*</span>}</>,
    },
    { key: 'total_vs_league', label: 'vs League', align: 'right', render: v => <DiffText value={v} /> },
    { key: 'avg_diff', label: 'Per Wk', align: 'right', render: v => <DiffText value={v} /> },
    { key: 'recent_avg_diff', label: 'Last 3', align: 'right', render: v => <DiffText value={v} /> },
    ...weeks.map(w => ({ key: `w${w}`, label: `W${w}`, align: 'right', render: v => <WeekCell value={v} /> })),
    {
      key: 'efficiency_pct', label: 'Efficiency', align: 'right',
      render: v => v == null ? '—' : (
        <span style={{ fontWeight: 600, color: v === bestEff ? 'var(--green)' : v === worstEff ? 'var(--brand-red)' : 'var(--text-primary)' }}>
          {fmt1(v)}%
        </span>
      ),
    },
    {
      key: 'pts_left_on_bench', label: 'Left on Bench', align: 'right',
      render: v => v == null ? '—' : <span style={{ color: 'var(--text-muted)' }}>{fmt1(v)}</span>,
    },
  ]

  if (loadSeasons) return <LoadingSpinner />

  return (
    <div>
      {seasons.length > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-faint)' }}>Season</span>
          <select
            value={season ?? ''}
            onChange={e => setSelectedSeason(Number(e.target.value))}
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-mid)', borderRadius: '6px', padding: '5px 10px', fontSize: '13px', color: 'var(--text-primary)', fontFamily: 'var(--font-body)', outline: 'none' }}
          >
            {seasons.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      )}

      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span className="fs-title" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Players vs Projection</span>
          <span className="fs-label" style={{ color: 'var(--text-faint)' }}>Season +/- through Wk {weeks[weeks.length - 1] ?? '—'}</span>
          {data?.league_avg_diff != null && (
            <span className="fs-label" style={{ color: 'var(--text-faint)' }} title="Average over/under per team per week, league-wide. Non-zero means Sleeper's projections ran high or low for everyone this season.">
              · League avg {signed(data.league_avg_diff)} per team-week
            </span>
          )}
          <span className="fs-label" style={{ marginLeft: 'auto', color: 'var(--text-faint)' }}>Efficiency columns = lineup decisions</span>
        </div>
        <p className="fs-body" style={{ color: 'var(--text-faint)', margin: 0, padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
          Did each team's starters score more or less than Sleeper projected? +20 means the players
          beat their projections by 20 points that week. Lineup efficiency is separate: it shows how
          good the manager's start/sit choices were, not how the players performed.
        </p>
        {data?.estimated_starters ? (
          <p className="fs-label" style={{ margin: 0, padding: '6px 14px', color: 'var(--text-faint)', borderBottom: '1px solid var(--border)' }}>
            * {data.estimated_starters} starter-weeks use a season-average stand-in projection, because Sleeper no longer has weekly projections for those players (retired or released since).
          </p>
        ) : null}
        {data?.excluded_pts ? (
          <p className="fs-label" style={{ margin: 0, padding: '6px 14px', color: 'var(--text-faint)', borderBottom: '1px solid var(--border)' }}>
            Left out: {data.excluded_starters} starter-weeks ({fmt1(data.excluded_pts)} pts) where Sleeper had no projection.
          </p>
        ) : null}
        {isLoading ? (
          <div style={{ padding: '20px' }}><LoadingSpinner /></div>
        ) : rows.length === 0 ? (
          <p className="fs-body" style={{ padding: '16px', color: 'var(--text-faint)', fontStyle: 'italic' }}>No projection data for this season yet.</p>
        ) : (
          <DataTable
            rows={rows}
            columns={columns}
            defaultSort="total_diff"
            defaultDir="desc"
            maxHeight="none"
            minWidth="900px"
            bordered={false}
          />
        )}
        <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
          <p style={{ fontSize: '11px', color: 'var(--text-faint)', margin: 0 }}>
            Projections are Sleeper's own for that week, summed over the players actually started.
            A starter with no weekly projection who scored (Sleeper drops players who later retire or get
            released) uses his season-long per-game projection instead, marked *. One with no projection of
            any kind, or who was inactive, is left out, so he can't show up as over-performance.
            vs League subtracts each week's league-wide average over/under, so seasons where
            Sleeper's projections ran high or low for everyone compare fairly. Efficiency is actual
            points as a % of the best possible lineup in hindsight; Left on Bench is the points
            between the two. Regular season only.
          </p>
        </div>
      </div>
      {/* Player detail: same table as the owner dashboard, starters only, for one owner */}
      <div ref={detailRef} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', marginTop: '20px' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span className="fs-title" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Player detail</span>
          <span className="fs-label" style={{ color: 'var(--text-faint)' }}>Starters only · weeks in the starting lineup</span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-faint)' }}>Owner</span>
            <select
              value={activeDetailOwner ?? ''}
              onChange={e => setDetailOwner(e.target.value)}
              style={{ background: 'var(--bg-page)', border: '1px solid var(--border-mid)', borderRadius: '6px', padding: '4px 10px', fontSize: '13px', color: 'var(--text-primary)', fontFamily: 'var(--font-body)', outline: 'none' }}
            >
              {[...ownerNames].sort().map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
        </div>
        <div style={{ padding: '14px' }}>
          {activeDetailOwner && <PlayerProjectionTable owner={activeDetailOwner} season={season} mode="starter" />}
        </div>
      </div>
    </div>
  )
}
