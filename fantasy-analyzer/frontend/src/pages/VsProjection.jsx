/**
 * VsProjection.jsx — how each owner's starters performed vs. Sleeper's projections.
 * Rendered inside the In-Season page (below the Playoff Picture), which passes its season in.
 *
 * One row per owner. "Players vs projection" columns show the actual points
 * their starters scored minus the sum of those starters' own Sleeper
 * projections (+20 = starters beat projection by 20), per week (W1, W2, ...),
 * for the season, per week on average, and over the last 3 weeks. This is
 * about the players, not the manager's choices.
 *
 * "Lineup decisions" columns (Efficiency, Left on Bench) are a separate
 * measure of the manager's start/sit: actual score as a % of the best lineup
 * in hindsight, and the points left on the bench.
 *
 * Data: /api/in-season/projection-performance/{season}. Click any header to sort.
 *
 * Props:
 *   season  {number} — season to show (the In-Season page's selected season)
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'

// ─── Helpers ──────────────────────────────────────────────────────────────────

const fmt1 = v => Number(v).toFixed(1)

function signed(v) {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${fmt1(v)}`
}

function diffColor(v) {
  if (v == null || Math.abs(v) < 0.05) return 'var(--text-muted)'
  return v > 0 ? 'var(--green)' : 'var(--brand-red)'
}

// Colored text for a +/- value (season, per week, last 3).
function DiffText({ value, bold = false }) {
  return <span style={{ color: diffColor(value), fontWeight: bold ? 700 : 500 }}>{signed(value)}</span>
}

// One weekly cell: tinted by size so hot/cold weeks stand out at a glance.
function WeekCell({ value }) {
  if (value == null) return <span style={{ color: 'var(--text-faint)' }}>—</span>
  const strength = Math.min(Math.abs(value) / 50, 1) * 0.28
  const rgb = value >= 0 ? '63,185,80' : '204,31,46'
  return (
    <span style={{
      display: 'inline-block', minWidth: '52px', textAlign: 'center', borderRadius: '4px', padding: '2px 4px',
      fontSize: '12px', fontWeight: 600, color: diffColor(value), background: `rgba(${rgb},${strength})`,
    }}>
      {signed(value)}
    </span>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function VsProjection({ season }) {
  const { data, isLoading } = useQuery({
    queryKey: ['projection-performance', season],
    queryFn: () => fetch(`/api/in-season/projection-performance/${season}`).then(r => r.json()),
    enabled: !!season,
  })

  const weeks = data?.weeks ?? []

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
    { key: 'owner', label: 'Owner', render: v => <span style={{ fontWeight: 600 }}>{v}</span> },
    { key: 'total_diff', label: 'Season +/-', align: 'right', render: v => <DiffText value={v} bold /> },
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

  if (!isLoading && rows.length === 0) return null

  return (
    <div style={{ marginTop: '20px' }}>
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span className="fs-title" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Players vs Projection</span>
          <span className="fs-label" style={{ color: 'var(--text-faint)' }}>Season +/- through Wk {weeks[weeks.length - 1] ?? '—'}</span>
          <span className="fs-label" style={{ marginLeft: 'auto', color: 'var(--text-faint)' }}>Efficiency columns = lineup decisions</span>
        </div>
        <p className="fs-body" style={{ color: 'var(--text-faint)', margin: 0, padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
          Did each team's starters score more or less than Sleeper projected? +20 means the players
          beat their projections by 20 points that week. Lineup efficiency is separate: it shows how
          good the manager's start/sit choices were, not how the players performed.
        </p>
        {isLoading ? (
          <div style={{ padding: '20px' }}><LoadingSpinner /></div>
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
            Projections are Sleeper's own for that week, summed over the players actually started
            (a starter with no projection, such as an injured player, counts as 0 projected).
            Efficiency is actual points as a % of the best possible lineup in hindsight; Left on
            Bench is the points between the two. Regular season only.
          </p>
        </div>
      </div>
    </div>
  )
}
