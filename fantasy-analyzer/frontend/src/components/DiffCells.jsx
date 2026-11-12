/**
 * DiffCells.jsx — shared display bits for "actual minus projection" numbers,
 * used by the league Vs Projection page and the owner Vs Projection tab.
 *
 *   fmt1(v)      — number to one decimal
 *   signed(v)    — "+12.3" / "-4.0" / "—" for null
 *   DiffText     — colored +/- text (green over, red under)
 *   WeekCell     — one weekly cell, tinted by size so hot/cold weeks stand out.
 *                  Pass dim to fade it (e.g. a week the player sat on the bench) and
 *                  est to add an asterisk (the projection was a season-average stand-in).
 */
export const fmt1 = v => Number(v).toFixed(1)

export function signed(v) {
  if (v == null) return '—'
  return `${v > 0 ? '+' : ''}${fmt1(v)}`
}

export function diffColor(v) {
  if (v == null || Math.abs(v) < 0.05) return 'var(--text-muted)'
  return v > 0 ? 'var(--green)' : 'var(--brand-red)'
}

export function DiffText({ value, bold = false }) {
  return <span style={{ color: diffColor(value), fontWeight: bold ? 700 : 500 }}>{signed(value)}</span>
}

export function WeekCell({ value, dim = false, est = false }) {
  if (value == null) return <span style={{ color: 'var(--text-faint)' }}>—</span>
  const strength = Math.min(Math.abs(value) / 50, 1) * 0.28
  const rgb = value >= 0 ? '63,185,80' : '204,31,46'
  return (
    <span style={{
      display: 'inline-block', minWidth: '52px', textAlign: 'center', borderRadius: '4px', padding: '2px 4px',
      fontSize: '12px', fontWeight: 600, color: diffColor(value), background: `rgba(${rgb},${strength})`,
      opacity: dim ? 0.45 : 1,
    }}>
      {signed(value)}{est ? '*' : ''}
    </span>
  )
}
