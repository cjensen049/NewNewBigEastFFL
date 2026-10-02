/**
 * PlayoffPctBadge.jsx — the colored playoff-odds pill shown on both the
 * Power Rankings and Playoff Picture pages.
 *
 * Renders "IN" / "OUT" only when the backend says a team has mathematically
 * clinched / been eliminated; otherwise the Monte Carlo % (already clamped to
 * 1–99% by the backend), colored by how likely it is. Keeping this in one
 * place is what guarantees both pages show the same number the same way.
 *
 * Props: pct {number}, clinched {boolean}, eliminated {boolean}
 */
function playoffStyle(pct, clinched, eliminated) {
  if (clinched)   return { color: 'var(--green)',     bg: 'rgba(63,185,80,0.15)',  border: 'rgba(63,185,80,0.35)',  label: 'IN' }
  if (eliminated) return { color: 'var(--brand-red)', bg: 'rgba(204,31,46,0.12)',  border: 'rgba(204,31,46,0.3)',   label: 'OUT' }
  if (pct >= 70)  return { color: 'var(--green)',     bg: 'rgba(63,185,80,0.12)',  border: 'rgba(63,185,80,0.25)',  label: null }
  if (pct >= 40)  return { color: 'var(--gold)',      bg: 'rgba(227,179,65,0.12)', border: 'rgba(227,179,65,0.3)',  label: null }
  return                 { color: 'var(--brand-red)', bg: 'rgba(204,31,46,0.1)',   border: 'rgba(204,31,46,0.25)',  label: null }
}

export default function PlayoffPctBadge({ pct, clinched, eliminated }) {
  const ps = playoffStyle(pct, clinched, eliminated)
  return ps.label ? (
    <span style={{ background: ps.bg, color: ps.color, border: `1px solid ${ps.border}`, borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 700, letterSpacing: '0.5px' }}>
      {ps.label}
    </span>
  ) : (
    <span style={{ background: ps.bg, color: ps.color, border: `1px solid ${ps.border}`, borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 600 }}>
      {(pct ?? 0).toFixed(0)}%
    </span>
  )
}
