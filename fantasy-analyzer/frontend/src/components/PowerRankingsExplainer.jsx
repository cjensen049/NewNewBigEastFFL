/**
 * PowerRankingsExplainer.jsx — static visual explainer for the power rankings formula.
 *
 * Four sections:
 *   1. Formula row     — pills showing how the four components combine into a power score
 *   2. Component cards — icon, name, 1–2 sentence description, colored badge
 *   3. Phase table     — weights by season phase with inline bar visualizations
 *   4. Example card    — sample team breakdown with horizontal bar chart per component
 */

// ─── Design constants ─────────────────────────────────────────────────────────

const COMP = {
  scoring: { solid: '#5b8dd9', bg: 'rgba(91,141,217,0.12)',  border: 'rgba(91,141,217,0.25)' },
  record:  { solid: '#3fb950', bg: 'rgba(63,185,80,0.12)',   border: 'rgba(63,185,80,0.25)'  },
  sos:     { solid: '#e3b341', bg: 'rgba(227,179,65,0.12)',  border: 'rgba(227,179,65,0.25)' },
  roster:  { solid: '#e05a5a', bg: 'rgba(224,90,90,0.12)',   border: 'rgba(224,90,90,0.25)'  },
}

const COMPONENT_CARDS = [
  {
    id:    'scoring',
    icon:  '📈',
    label: 'Scoring',
    badge: 'Recent weeks favored',
    desc:  'Exponentially weighted average of weekly scores (decay = 0.85). Last week counts nearly twice as much as three weeks ago.',
  },
  {
    id:    'record',
    icon:  '⚔️',
    label: 'All-play Record',
    badge: 'Luck adjusted',
    desc:  'Every team vs. every other team each week produces a true win rate, stripping schedule luck from the standings.',
  },
  {
    id:    'sos',
    icon:  '🗓️',
    label: 'Schedule Strength',
    badge: 'Early season only',
    desc:  "Average win% of remaining opponents, inverted — an easier remaining schedule scores higher. Weight fades as weeks accumulate.",
  },
  {
    id:    'roster',
    icon:  '🏈',
    label: 'Roster Quality',
    badge: 'Auto-updated',
    desc:  "FantasyPros projected optimal lineup score, scraped weekly. Carries heavy weight early before game results tell the story.",
  },
]

// Intended steady-state weights (when FantasyPros data is available)
const PHASES = [
  { label: 'Early', weeks: 'Wks 1–4',   scoring: 15, record: 10, sos: 25, roster: 50 },
  { label: 'Mid',   weeks: 'Wks 5–10',  scoring: 35, record: 30, sos: 10, roster: 25 },
  { label: 'Late',  weeks: 'Wks 11–14', scoring: 45, record: 35, sos:  5, roster: 15 },
]

// ─── Shared primitives ────────────────────────────────────────────────────────

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: '10px', fontWeight: 600, letterSpacing: '1.5px',
      textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '10px',
    }}>
      {children}
    </div>
  )
}

function MiniBar({ value, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
      <span style={{
        fontVariantNumeric: 'tabular-nums', fontSize: '12px',
        color: 'var(--text-muted)', width: '30px', flexShrink: 0,
      }}>
        {value}%
      </span>
      <div style={{ flex: 1, height: '6px', background: 'var(--border)', borderRadius: '3px', overflow: 'hidden', minWidth: '60px' }}>
        <div style={{ width: `${value * 2}%`, height: '100%', background: color, borderRadius: '3px' }} />
      </div>
    </div>
  )
}

// ─── Section 1: Formula row ───────────────────────────────────────────────────

function FormulaRow() {
  const pills = [
    { id: 'scoring', label: 'Scoring' },
    { id: 'record',  label: 'All-play Record' },
    { id: 'sos',     label: 'Schedule' },
    { id: 'roster',  label: 'Roster Quality' },
  ]

  return (
    <div style={{ marginBottom: '28px' }}>
      <SectionLabel>Formula</SectionLabel>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
        {pills.map((p, i) => (
          <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              background: COMP[p.id].bg,
              color: COMP[p.id].solid,
              border: `1px solid ${COMP[p.id].border}`,
              borderRadius: '6px',
              padding: '5px 13px',
              fontSize: '13px',
              fontWeight: 600,
              whiteSpace: 'nowrap',
            }}>
              {p.label}
            </span>
            {i < pills.length - 1 && (
              <span style={{ color: 'var(--text-faint)', fontSize: '16px', fontWeight: 300, lineHeight: 1 }}>+</span>
            )}
          </div>
        ))}
        <span style={{ color: 'var(--text-faint)', fontSize: '16px', fontWeight: 300, lineHeight: 1 }}>=</span>
        <span style={{
          background: 'var(--bg-raised)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-mid)',
          borderRadius: '6px',
          padding: '5px 13px',
          fontSize: '13px',
          fontWeight: 700,
          whiteSpace: 'nowrap',
          letterSpacing: '0.3px',
        }}>
          Power Score
        </span>
      </div>
    </div>
  )
}

// ─── Section 2: Component cards ──────────────────────────────────────────────

function ComponentCards() {
  return (
    <div style={{ marginBottom: '28px' }}>
      <SectionLabel>Components</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
        {COMPONENT_CARDS.map(c => {
          const col = COMP[c.id]
          return (
            <div key={c.id} style={{
              background: 'var(--bg-surface)',
              border: `1px solid var(--border)`,
              borderLeft: `3px solid ${col.solid}`,
              borderRadius: '8px',
              padding: '14px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '7px' }}>
                <span style={{ fontSize: '16px', lineHeight: 1 }}>{c.icon}</span>
                <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{c.label}</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.55, margin: '0 0 10px' }}>
                {c.desc}
              </p>
              <span style={{
                display: 'inline-block',
                background: col.bg,
                color: col.solid,
                border: `1px solid ${col.border}`,
                borderRadius: '4px',
                padding: '2px 7px',
                fontSize: '10px',
                fontWeight: 600,
                letterSpacing: '0.3px',
              }}>
                {c.badge}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Section 3: Phase weights table ──────────────────────────────────────────

function PhaseTable() {
  const cols = [
    { id: 'scoring', label: 'Scoring' },
    { id: 'record',  label: 'Record'  },
    { id: 'sos',     label: 'Schedule' },
    { id: 'roster',  label: 'Roster'  },
  ]

  const TH = ({ children, color }) => (
    <th style={{
      padding: '8px 12px',
      textAlign: 'left',
      fontSize: '10px',
      fontWeight: 600,
      letterSpacing: '1px',
      textTransform: 'uppercase',
      color: color ?? 'var(--text-faint)',
      background: 'var(--bg-page)',
      borderBottom: '1px solid var(--border)',
      whiteSpace: 'nowrap',
    }}>
      {children}
    </th>
  )

  return (
    <div style={{ marginBottom: '28px' }}>
      <SectionLabel>Phase Weights</SectionLabel>
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '480px' }}>
            <thead>
              <tr>
                <TH>Phase</TH>
                {cols.map(c => <TH key={c.id} color={COMP[c.id].solid}>{c.label}</TH>)}
              </tr>
            </thead>
            <tbody>
              {PHASES.map((phase, i) => (
                <tr key={phase.label} style={{ borderBottom: i < PHASES.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <td style={{ padding: '10px 12px', whiteSpace: 'nowrap', verticalAlign: 'middle' }}>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{phase.label}</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-faint)', marginTop: '2px' }}>{phase.weeks}</div>
                  </td>
                  {cols.map(c => (
                    <td key={c.id} style={{ padding: '10px 12px', minWidth: '120px', verticalAlign: 'middle' }}>
                      <MiniBar value={phase[c.id]} color={COMP[c.id].solid} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ padding: '7px 12px', borderTop: '1px solid var(--border)', background: 'var(--bg-page)' }}>
          <p style={{ fontSize: '10px', color: 'var(--text-faint)', margin: 0 }}>
            When FantasyPros projections are unavailable, Roster weight redistributes proportionally to Schedule Strength.
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── Root export ──────────────────────────────────────────────────────────────

export default function PowerRankingsExplainer() {
  return (
    <div style={{ paddingTop: '4px' }}>
      <FormulaRow />
      <ComponentCards />
      <PhaseTable />
    </div>
  )
}
