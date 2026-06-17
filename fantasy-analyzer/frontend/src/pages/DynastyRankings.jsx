/**
 * DynastyRankings.jsx — Long-term dynasty power rankings panel.
 *
 * Ranks all 12 owners by dynasty strength using three components:
 *   Roster Score   (55%) — player values from the selected source; taxi at 80%
 *   Capital Score  (30%) — Future draft picks owned × pick tier values
 *   Age Score      (15%) — Value-weighted avg age; younger rosters score higher
 *
 * All component scores are normalised 0–100 within the league.
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

function scoreBar(value) {
  const v = value ?? 0
  const color = v >= 70 ? 'var(--green)' : v >= 40 ? 'var(--gold)' : 'var(--brand-red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{ flex: 1, height: '4px', background: 'var(--border)', borderRadius: '2px', minWidth: '40px' }}>
        <div style={{ width: `${v}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width 0.3s' }} />
      </div>
      <span style={{ fontSize: '11px', fontVariantNumeric: 'tabular-nums', color, fontWeight: 600, minWidth: '28px', textAlign: 'right' }}>
        {v.toFixed(0)}
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
    weight: '55%',
    color: '#5b8dd9',
    bg: 'rgba(26,58,107,0.15)',
    border: 'rgba(91,141,217,0.2)',
    desc: 'Every player on your roster valued using the selected source’s SuperFlex (2QB) ratings. Taxi squad players counted at 80% of full value.',
  },
  {
    label: 'Draft Capital',
    weight: '30%',
    color: 'var(--gold)',
    bg: 'rgba(227,179,65,0.1)',
    border: 'rgba(227,179,65,0.25)',
    desc: 'Combined value of all future rookie draft picks you currently own, covering the next 3 draft classes. Picks valued by round and tier (early/mid/late).',
  },
  {
    label: 'Age Score',
    weight: '15%',
    color: 'var(--green)',
    bg: 'rgba(63,185,80,0.08)',
    border: 'rgba(63,185,80,0.2)',
    desc: 'Value-weighted average age of your top 15 players. Dynasty prime is age 25 — each year older reduces your score. Rewards building young.',
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
          ? 'All three scores normalised 0–100 within NNBE, then combined per source. "Overall" averages each owner’s composite across every available source.'
          : 'All three scores normalised 0–100 within NNBE, then combined.'}
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
        {dataDate && (
          <span style={{ background: 'rgba(26,58,107,0.3)', color: '#5b8dd9', border: '1px solid rgba(91,141,217,0.2)', borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 600 }}>
            {dataDate}
          </span>
        )}
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-faint)' }}>
          {isOverall ? 'Average composite across sources' : 'Roster 55% · Capital 30% · Age 15%'}
        </span>
      </div>

      {SourceToggle}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '16px', minWidth: '400px' }}>
          <thead>
            <tr>
              <TH width="36px">#</TH>
              <TH>Owner</TH>
              <TH align="right" title="Composite dynasty score (0–100)">Score</TH>
              {isOverall ? (
                availableSources.map(s => (
                  <TH key={s} title={`${sourceLabel(s)} composite score, normalised 0–100`}>{sourceLabel(s)}</TH>
                ))
              ) : (
                <>
                  <TH title="Roster value from the selected source's SuperFlex values, normalised 0–100">Roster</TH>
                  <TH title="Future draft pick capital: picks owned × tier value, normalised 0–100">Capital</TH>
                  <TH title="Value-weighted avg age of top 15 players vs. dynasty prime (25). Younger = higher score, normalised 0–100">Age</TH>
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
                      {r.composite.toFixed(1)}
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
