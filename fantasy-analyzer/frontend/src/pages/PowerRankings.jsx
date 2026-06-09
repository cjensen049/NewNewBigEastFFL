/**
 * PowerRankings.jsx — In-season power rankings panel.
 *
 * Displays a ranked table of all 12 teams based on a weighted formula:
 *   Scoring component  (EWA of weekly scores, recent weeks weighted more)
 *   Record component   (luck-adjusted sim win%)
 *   SoS component      (inverse remaining schedule strength)
 *
 * Weights shift by season phase. Playoff% comes from a Monte Carlo
 * simulation of the remaining schedule (10,000 runs, NNBE rules).
 *
 * Props:
 *   season  {number} — active season year
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '../components/LoadingSpinner'
import PowerRankingsExplainer from '../components/PowerRankingsExplainer'

// Component score colours — must match PowerRankingsExplainer
const SCORE_COLORS = {
  scoring: '#5b8dd9',
  record:  '#3fb950',
  sos:     '#e3b341',
  roster:  '#e05a5a',
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function wlStyle(wins, losses) {
  if (wins > losses) return { background: 'rgba(63,185,80,0.12)',  color: 'var(--green)' }
  if (losses > wins) return { background: 'rgba(204,31,46,0.1)',   color: 'var(--brand-red)' }
  return                    { background: 'rgba(227,179,65,0.12)', color: 'var(--gold)' }
}

function rankStyle(rank) {
  if (rank === 1) return { bg: 'rgba(204,31,46,0.2)',  text: 'var(--brand-red)' }
  if (rank === 2) return { bg: 'rgba(26,58,107,0.3)',  text: '#5b8dd9' }
  if (rank === 3) return { bg: 'rgba(26,58,107,0.15)', text: '#5b8dd9' }
  return                 { bg: 'var(--border)',         text: 'var(--text-muted)' }
}

function playoffStyle(pct) {
  if (pct >= 99) return { color: 'var(--green)',     bg: 'rgba(63,185,80,0.15)',  border: 'rgba(63,185,80,0.35)',  label: 'IN' }
  if (pct <=  1) return { color: 'var(--brand-red)', bg: 'rgba(204,31,46,0.12)',  border: 'rgba(204,31,46,0.3)',   label: 'OUT' }
  // 2–98%: color by pct
  if (pct >= 70) return { color: 'var(--green)',     bg: 'rgba(63,185,80,0.12)',  border: 'rgba(63,185,80,0.25)',  label: null }
  if (pct >= 40) return { color: 'var(--gold)',      bg: 'rgba(227,179,65,0.12)', border: 'rgba(227,179,65,0.3)',  label: null }
  return                { color: 'var(--brand-red)', bg: 'rgba(204,31,46,0.1)',   border: 'rgba(204,31,46,0.25)',  label: null }
}

const PHASE_BADGE = {
  early: { color: '#e3b341', bg: 'rgba(227,179,65,0.15)', border: 'rgba(227,179,65,0.35)' },
  mid:   { color: '#5b8dd9', bg: 'rgba(26,58,107,0.25)',  border: 'rgba(91,141,217,0.3)' },
  late:  { color: '#e05a5a', bg: 'rgba(204,31,46,0.15)',  border: 'rgba(204,31,46,0.35)' },
}

function pct(w) { return Math.round(w * 100) + '%' }

// ─── Panel header ─────────────────────────────────────────────────────────────

function PanelHeader({ currentWeek, phaseKey, phaseLabel, weights, isFallback, displaySeason }) {
  const pb = PHASE_BADGE[phaseKey] ?? PHASE_BADGE.mid

  return (
    <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
      <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
        Power Rankings
      </span>

      {isFallback ? (
        <span style={{ background: 'rgba(227,179,65,0.12)', color: 'var(--gold)', border: '1px solid rgba(227,179,65,0.3)', borderRadius: '4px', padding: '2px 7px', fontSize: '10px', fontWeight: 600 }}>
          FINAL {displaySeason}
        </span>
      ) : (
        currentWeek > 0 && (
          <span style={{ background: 'rgba(26,58,107,0.3)', color: '#5b8dd9', border: '1px solid rgba(91,141,217,0.2)', borderRadius: '4px', padding: '2px 7px', fontSize: '10px', fontWeight: 600 }}>
            WK {currentWeek}
          </span>
        )
      )}

      {!isFallback && (
        <span style={{ background: pb.bg, color: pb.color, border: `1px solid ${pb.border}`, borderRadius: '4px', padding: '2px 7px', fontSize: '10px', fontWeight: 600, letterSpacing: '0.5px' }}>
          {phaseLabel.toUpperCase()}
        </span>
      )}

      <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-faint)' }}>
        Scoring {pct(weights.scoring)} · Record {pct(weights.record)} · SoS {pct(weights.sos)}
      </span>
    </div>
  )
}

// ─── Trend indicator ──────────────────────────────────────────────────────────

function Trend({ value, isFirstWeek }) {
  if (isFirstWeek || value === 0) {
    return <span style={{ color: 'var(--text-faint)', fontSize: '11px' }}>—</span>
  }
  if (value > 0) {
    return (
      <span style={{ color: 'var(--green)', fontSize: '11px', fontWeight: 600 }}>
        ▲{value}
      </span>
    )
  }
  return (
    <span style={{ color: 'var(--brand-red)', fontSize: '11px', fontWeight: 600 }}>
      ▼{Math.abs(value)}
    </span>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

// ─── How it works toggle ──────────────────────────────────────────────────────

function HowItWorks() {
  const [open, setOpen] = useState(true)
  return (
    <div style={{ marginBottom: '20px' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-faint)', fontSize: '12px', fontWeight: 500,
          padding: '4px 0', marginBottom: open ? '14px' : 0,
          transition: 'color 0.15s',
        }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--text-muted)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text-faint)'}
      >
        <span style={{ fontSize: '10px', display: 'inline-block', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>▶</span>
        How rankings are calculated
      </button>
      {open && <PowerRankingsExplainer />}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function PowerRankings({ season }) {
  const { data, isLoading } = useQuery({
    queryKey: ['power-rankings', season],
    queryFn: () => fetch(`/api/in-season/power-rankings/${season}`).then(r => r.json()),
    enabled: !!season,
  })

  const currentRows = data?.rows ?? []
  const noCurrentData = !isLoading && currentRows.length === 0

  // When the new season hasn't started, fall back to the prior season's final rankings
  const { data: prevData, isLoading: prevLoading } = useQuery({
    queryKey: ['power-rankings', season - 1],
    queryFn: () => fetch(`/api/in-season/power-rankings/${season - 1}`).then(r => r.json()),
    enabled: noCurrentData && !!season,
  })

  if (isLoading || (noCurrentData && prevLoading)) {
    return <div style={{ padding: '20px 0' }}><LoadingSpinner /></div>
  }

  const isFallback    = noCurrentData && (prevData?.rows ?? []).length > 0
  const display       = isFallback ? prevData : data
  const rows          = display?.rows ?? []
  const currentWeek   = display?.current_week ?? 0
  const phaseKey      = display?.phase ?? 'mid'
  const phaseLabel    = display?.phase_label ?? 'Mid Season'
  const weights       = display?.weights ?? { scoring: 0.45, record: 0.40, sos: 0.15 }
  const displaySeason = isFallback ? season - 1 : season

  const [expandedRank, setExpandedRank] = useState(null)

  if (rows.length === 0) {
    return (
      <>
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', marginBottom: '20px' }}>
          <PanelHeader currentWeek={0} phaseKey="early" phaseLabel="Early Season" weights={{ scoring: 0.25, record: 0.20, sos: 0.55 }} />
          <p style={{ padding: '24px 16px', fontSize: '13px', color: 'var(--text-faint)', fontStyle: 'italic', textAlign: 'center' }}>
            Power rankings available once the season begins.
          </p>
        </div>
        <HowItWorks />
      </>
    )
  }

  const isFirstWeek = currentWeek <= 1

  const TH = ({ children, align = 'left', title }) => (
    <th title={title} style={{
      padding: '8px 10px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px',
      textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)',
      borderBottom: '1px solid var(--border)', textAlign: align, whiteSpace: 'nowrap',
    }}>
      {children}
    </th>
  )

  return (
  <>
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', marginBottom: '20px' }}>
      <PanelHeader currentWeek={currentWeek} phaseKey={phaseKey} phaseLabel={phaseLabel} weights={weights} isFallback={isFallback} displaySeason={displaySeason} />
      {isFallback && (
        <div style={{ padding: '7px 14px', background: 'rgba(227,179,65,0.06)', borderBottom: '1px solid rgba(227,179,65,0.15)', fontSize: '11px', color: 'var(--text-faint)' }}>
          Showing final {displaySeason} rankings — {season} rankings will appear once the season begins.
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '16px', minWidth: '480px' }}>
          <thead>
            <tr>
              <TH>#</TH>
              <TH title="Change vs. last week">▲▼</TH>
              <TH>Owner</TH>
              <TH align="right" title={`Scoring ${pct(weights.scoring)} · Record ${pct(weights.record)} · SoS ${pct(weights.sos)}`}>Power</TH>
              <TH align="right" title="Monte Carlo playoff probability (10,000 simulations)">Playoff%</TH>
              <TH align="right">W-L</TH>
              <TH align="right">Pts For</TH>
              <TH></TH>
            </tr>
          </thead>
          {rows.map((r) => {
              const rs = rankStyle(r.rank)
              const wl = wlStyle(r.actual_wins, r.actual_losses)
              const ps = playoffStyle(r.playoff_pct)
              const pts = r.pts_for != null
                ? Number(r.pts_for).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
                : '—'
              const isExpanded = expandedRank === r.rank

              const scoreItems = [
                { key: 'scoring', label: 'Scoring',         value: r.scoring_score ?? 0 },
                { key: 'record',  label: 'All-play Record', value: r.record_score  ?? 0 },
                { key: 'sos',     label: 'Schedule',        value: r.sos_score     ?? 0 },
                ...(r.roster_score != null ? [{ key: 'roster', label: 'Roster Quality', value: r.roster_score }] : []),
              ]

              return (
                <tbody key={r.rank}>
                  <tr
                    className="standings-row"
                    onClick={() => setExpandedRank(isExpanded ? null : r.rank)}
                    style={{ borderBottom: isExpanded ? 'none' : '1px solid var(--border)', cursor: 'pointer' }}
                  >
                    {/* Rank */}
                    <td style={{ padding: '8px 10px', width: '36px' }}>
                      <div style={{ width: '22px', height: '22px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 700, background: rs.bg, color: rs.text }}>
                        {r.rank}
                      </div>
                    </td>

                    {/* Trend */}
                    <td style={{ padding: '8px 6px', width: '32px', textAlign: 'center' }}>
                      <Trend value={r.trend} isFirstWeek={isFirstWeek} />
                    </td>

                    {/* Owner */}
                    <td style={{ padding: '8px 10px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                      {r.owner}
                    </td>

                    {/* Power score */}
                    <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <span style={{ fontFamily: 'var(--font-display)', fontSize: '16px', letterSpacing: '0.5px', color: 'var(--text-primary)', lineHeight: 1 }}>
                        {(r.power_score ?? 0).toFixed(1)}
                      </span>
                    </td>

                    {/* Playoff % */}
                    <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {ps.label ? (
                        <span style={{ background: ps.bg, color: ps.color, border: `1px solid ${ps.border}`, borderRadius: '4px', padding: '2px 7px', fontSize: '10px', fontWeight: 700, letterSpacing: '0.5px' }}>
                          {ps.label}
                        </span>
                      ) : (
                        <span style={{ background: ps.bg, color: ps.color, border: `1px solid ${ps.border}`, borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 600 }}>
                          {(r.playoff_pct ?? 0).toFixed(0)}%
                        </span>
                      )}
                    </td>

                    {/* W-L */}
                    <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <span style={{ ...wl, borderRadius: '4px', padding: '2px 5px', fontSize: '11px', fontWeight: 600 }}>
                        {r.actual_wins}-{r.actual_losses}
                      </span>
                    </td>

                    {/* Pts For */}
                    <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                      {pts}
                    </td>

                    {/* Expand chevron */}
                    <td style={{ padding: '8px 10px', width: '28px', textAlign: 'right' }}>
                      <span style={{
                        display: 'inline-block',
                        fontSize: '9px',
                        color: 'var(--text-faint)',
                        transform: isExpanded ? 'rotate(90deg)' : 'none',
                        transition: 'transform 0.15s',
                      }}>▶</span>
                    </td>
                  </tr>

                  {/* Expanded breakdown row */}
                  {isExpanded && (
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      <td colSpan={8} style={{ padding: '0 14px 12px 14px', background: 'var(--bg-page)' }}>
                        <div style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                          gap: '8px 20px',
                          paddingTop: '10px',
                        }}>
                          {scoreItems.map(item => (
                            <div key={item.key} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted)', width: '108px', flexShrink: 0 }}>
                                {item.label}
                              </span>
                              <div style={{ flex: 1, height: '7px', background: 'var(--border)', borderRadius: '4px', overflow: 'hidden', minWidth: '60px' }}>
                                <div style={{
                                  width: `${item.value}%`,
                                  height: '100%',
                                  background: SCORE_COLORS[item.key],
                                  borderRadius: '4px',
                                }} />
                              </div>
                              <span style={{ fontSize: '11px', fontWeight: 600, color: SCORE_COLORS[item.key], width: '26px', textAlign: 'right', flexShrink: 0 }}>
                                {Math.round(item.value)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              )
            })}
        </table>
      </div>

      {/* Footer note */}
      <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)' }}>
        <p style={{ fontSize: '10px', color: 'var(--text-faint)', margin: 0 }}>
          {isFallback
            ? `Final ${displaySeason} regular-season standings · Playoff% reflects end-of-season simulation`
            : 'Playoff% via 10,000 Monte Carlo simulations · NNBE rules: top 4 by record, next 2 by points'}
        </p>
      </div>
    </div>

    <HowItWorks />
  </>
  )
}
