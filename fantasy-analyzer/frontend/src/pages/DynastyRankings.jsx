/**
 * DynastyRankings.jsx — Long-term dynasty power rankings panel.
 *
 * Ranks all 12 owners by dynasty strength using three components:
 *   Roster Score   (60%) — the source's own published team total when it has
 *                          one (KTC), else sum of player values; taxi at 80%
 *   Capital Score  (35%) — Future draft picks owned × the source's own pick values
 *   Age Score       (5%) — Plain avg age across the full roster incl. taxi;
 *                          younger rosters score higher
 *
 * All component scores (and the composite) are untethered z-scores — how many
 * standard deviations above/below the league average a team is. 0 = average;
 * there's no fixed ceiling, so a real outlier (e.g. a team holding most of the
 * league's first-round picks) can show up far above everyone else instead of
 * being compressed toward a 0–100 cap.
 * A source toggle lets you view the ranking using a single valuation site
 * (DynastyProcess, FantasyCalc, ...) or "Overall", which averages each
 * owner's composite score across every source that has data.
 * Refreshed 4× per year: post rookie draft, Week 1, post trade deadline,
 * and post championship.
 *
 * Props:
 *   season  {number} — active season year
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '../components/LoadingSpinner'

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SOURCE_LABELS = {
  overall: 'Overall',
  dynastyprocess: 'DynastyProcess',
  fantasycalc: 'FantasyCalc',
  ktc: 'KeepTradeCut',
}

function sourceLabel(source) {
  return SOURCE_LABELS[source] ?? source
}

function rankStyle(rank) {
  if (rank === 1) return { bg: 'rgba(204,31,46,0.2)',  text: 'var(--brand-red)' }
  if (rank === 2) return { bg: 'rgba(26,58,107,0.3)',  text: '#5b8dd9' }
  if (rank === 3) return { bg: 'rgba(26,58,107,0.15)', text: '#5b8dd9' }
  return                 { bg: 'var(--border)',         text: 'var(--text-muted)' }
}

// Scores are untethered z-scores (typically roughly -2.5..+2.5, occasionally
// further out for a real outlier). Clamp just for the bar's visual width —
// the displayed number is always the raw, unclamped z-score.
const _Z_BAR_RANGE = 2.5

function scoreBar(value) {
  const v = value ?? 0
  const clamped = Math.max(-_Z_BAR_RANGE, Math.min(_Z_BAR_RANGE, v))
  const pct = ((clamped + _Z_BAR_RANGE) / (2 * _Z_BAR_RANGE)) * 100
  const color = v >= 1 ? 'var(--green)' : v >= -0.5 ? 'var(--gold)' : 'var(--brand-red)'
  const label = `${v >= 0 ? '+' : ''}${v.toFixed(2)}`
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{ flex: 1, height: '4px', background: 'var(--border)', borderRadius: '2px', minWidth: '40px' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width 0.3s' }} />
      </div>
      <span style={{ fontSize: '11px', fontVariantNumeric: 'tabular-nums', color, fontWeight: 600, minWidth: '38px', textAlign: 'right' }}>
        {label}
      </span>
    </div>
  )
}

// ─── Source toggle pills ────────────────────────────────────────────────────

function SourcePill({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '4px 12px',
        borderRadius: '5px',
        fontSize: '11px',
        fontWeight: 600,
        cursor: 'pointer',
        border: active ? '1px solid transparent' : '1px solid var(--border-mid)',
        background: active ? 'var(--brand-navy)' : 'var(--border)',
        color: active ? '#ffffff' : 'var(--text-muted)',
        transition: 'background 0.15s, color 0.15s',
      }}
    >
      {label}
    </button>
  )
}

// Three-card formula breakdown shown below the table
const FORMULA_CARDS = [
  {
    label: 'Roster Score',
    weight: '60%',
    color: '#5b8dd9',
    bg: 'rgba(26,58,107,0.15)',
    border: 'rgba(91,141,217,0.2)',
    desc: 'The source’s own published team total when it has one (KTC), else the sum of every player on your roster using the source’s SuperFlex (2QB) ratings — taxi squad at 80% of full value.',
  },
  {
    label: 'Draft Capital',
    weight: '35%',
    color: 'var(--gold)',
    bg: 'rgba(227,179,65,0.1)',
    border: 'rgba(227,179,65,0.25)',
    desc: 'Combined value of all future rookie draft picks you currently own, covering the next 3 draft classes, priced using the source’s own draft pick values.',
  },
  {
    label: 'Age Score',
    weight: '5%',
    color: 'var(--green)',
    bg: 'rgba(63,185,80,0.08)',
    border: 'rgba(63,185,80,0.2)',
    desc: 'Plain average age across your entire roster, including the taxi squad. Younger rosters score higher. Weighted lightly — it’s a tiebreaker, not a driver.',
  },
]

function FormulaFooter({ source }) {
  const isOverall = source === 'overall'
  return (
    <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)' }}>
      <p style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '0.8px', textTransform: 'uppercase', color: 'var(--text-faint)', margin: '0 0 8px' }}>
        How it's calculated
      </p>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {FORMULA_CARDS.map(c => (
          <div key={c.label} style={{
            flex: '1 1 180px',
            background: c.bg,
            border: `1px solid ${c.border}`,
            borderRadius: '8px',
            padding: '10px 12px',
          }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '5px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: c.color }}>{c.label}</span>
              <span style={{ fontSize: '11px', fontWeight: 600, color: c.color, opacity: 0.8 }}>{c.weight}</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
              {c.desc}
            </p>
          </div>
        ))}
      </div>
      <p style={{ fontSize: '11px', color: 'var(--text-faint)', margin: '8px 0 0' }}>
        {isOverall
          ? 'All three scores are untethered z-scores within NNBE (0 = league average), combined per source. "Overall" averages each owner’s composite across every available source — which also cancels out any one site systematically ranking a team higher or lower than the others.'
          : 'All three scores are untethered z-scores within NNBE — 0 = league average, positive/negative show how many standard deviations above/below average a team is.'}
        {' '}Values via {isOverall ? 'all available sources' : sourceLabel(source)} · refreshed 4× per year.
      </p>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function DynastyRankings({ season }) {
  const [source, setSource] = useState('overall')

  const { data, isLoading } = useQuery({
    queryKey: ['dynasty-rankings', season, source],
    queryFn: () => fetch(`/api/in-season/dynasty-rankings/${season}?source=${source}`).then(r => r.json()),
    enabled: !!season,
  })

  if (isLoading) return <div style={{ padding: '20px 0' }}><LoadingSpinner /></div>

  const rows             = data?.rows ?? []
  const dataDate         = data?.data_date ?? null
  const availableSources = data?.available_sources ?? []
  const isOverall         = source === 'overall'

  const pills = ['overall', ...availableSources]

  const SourceToggle = availableSources.length > 0 && (
    <div style={{ display: 'flex', gap: '6px', padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
      {pills.map(s => (
        <SourcePill key={s} active={source === s} onClick={() => setSource(s)} label={sourceLabel(s)} />
      ))}
    </div>
  )

  if (rows.length === 0) {
    return (
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', maxWidth: '700px' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Dynasty Rankings</span>
          <span style={{ background: 'rgba(227,179,65,0.12)', color: 'var(--gold)', border: '1px solid rgba(227,179,65,0.25)', borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 600 }}>
            {sourceLabel(source)}
          </span>
        </div>
        {SourceToggle}
        <p style={{ padding: '24px 16px', fontSize: '13px', color: 'var(--text-faint)', fontStyle: 'italic', textAlign: 'center' }}>
          Dynasty rankings refreshed 4× per year: post rookie draft, Week 1, post trade deadline, and post championship.
        </p>
        <FormulaFooter source={source} />
      </div>
    )
  }

  const TH = ({ children, align = 'left', title, width }) => (
    <th title={title} style={{
      padding: '8px 10px', fontSize: '11px', fontWeight: 600, letterSpacing: '1px',
      textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)',
      borderBottom: '1px solid var(--border)', textAlign: align, whiteSpace: 'nowrap',
      ...(width ? { width } : {}),
    }}>
      {children}
    </th>
  )

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', maxWidth: '700px' }}>
      {/* Panel header */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Dynasty Rankings
        </span>
        <span style={{ background: 'rgba(227,179,65,0.12)', color: 'var(--gold)', border: '1px solid rgba(227,179,65,0.25)', borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 600 }}>
          {sourceLabel(source)}
        </span>
        {dataDate && (
          <span style={{ background: 'rgba(26,58,107,0.3)', color: '#5b8dd9', border: '1px solid rgba(91,141,217,0.2)', borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 600 }}>
            {dataDate}
          </span>
        )}
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-faint)' }}>
          {isOverall ? 'Average composite across sources' : 'Roster 60% · Capital 35% · Age 5%'}
        </span>
      </div>

      {SourceToggle}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '16px', minWidth: '400px' }}>
          <thead>
            <tr>
              <TH width="36px">#</TH>
              <TH>Owner</TH>
              <TH align="right" title="Composite dynasty z-score — 0 is league average">Score</TH>
              {isOverall ? (
                availableSources.map(s => (
                  <TH key={s} title={`${sourceLabel(s)} composite z-score — 0 is league average`}>{sourceLabel(s)}</TH>
                ))
              ) : (
                <>
                  <TH title="Roster value z-score: the source's own published team total when it has one, else summed player values">Roster</TH>
                  <TH title="Future draft pick capital z-score: picks owned × the source's own pick values">Capital</TH>
                  <TH title="Age z-score: plain average age across the full roster incl. taxi squad. Younger = higher score">Age</TH>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const rs = rankStyle(r.rank)
              return (
                <tr key={r.rank} className="standings-row" style={{ borderBottom: '1px solid var(--border)' }}>
                  {/* Rank */}
                  <td style={{ padding: '8px 10px' }}>
                    <div style={{ width: '22px', height: '22px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700, background: rs.bg, color: rs.text }}>
                      {r.rank}
                    </div>
                  </td>

                  {/* Owner */}
                  <td style={{ padding: '8px 10px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                    {r.owner}
                  </td>

                  {/* Composite score */}
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: '16px', letterSpacing: '0.5px', color: 'var(--text-primary)', lineHeight: 1 }}>
                      {r.composite >= 0 ? '+' : ''}{r.composite.toFixed(2)}
                    </span>
                  </td>

                  {isOverall ? (
                    availableSources.map(s => (
                      <td key={s} style={{ padding: '6px 10px' }}>{scoreBar(r.source_scores?.[s])}</td>
                    ))
                  ) : (
                    <>
                      <td style={{ padding: '6px 10px' }}>{scoreBar(r.roster_score)}</td>
                      <td style={{ padding: '6px 10px' }}>{scoreBar(r.capital_score)}</td>
                      <td style={{ padding: '6px 10px' }}>{scoreBar(r.age_score)}</td>
                    </>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <FormulaFooter source={source} />
    </div>
  )
}
