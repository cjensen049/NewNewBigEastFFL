/**
 * Schedule.jsx — Upcoming season schedule.
 *
 * Fetches the most recent season's finish order (1-12) to determine next
 * year's divisions (Top 4 / Mid 4 / Bot 4) for the division-preview panel,
 * and the real per-week opponents from Sleeper's published matchup pairings
 * (GET /api/history/schedule/{season} — available before any games are
 * played). Falls back to a generated round-robin projection only if the
 * real schedule isn't in the database yet (e.g. season not drafted/synced).
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '../components/LoadingSpinner'

// ─── Division palette ─────────────────────────────────────────────────────────

const DIV = [
  {
    label: 'Top 4',
    range: '1st – 4th',
    text: '#e3b341',
    border: 'rgba(227,179,65,0.4)',
    hdr: 'rgba(227,179,65,0.2)',
    cellNormal: 'rgba(227,179,65,0.12)',
    cellInDiv: 'rgba(227,179,65,0.26)',
  },
  {
    label: 'Mid 4',
    range: '5th – 8th',
    text: '#5b8dd9',
    border: 'rgba(91,141,217,0.35)',
    hdr: 'rgba(26,58,107,0.35)',
    cellNormal: 'rgba(26,58,107,0.18)',
    cellInDiv: 'rgba(26,58,107,0.35)',
  },
  {
    label: 'Bot 4',
    range: '9th – 12th',
    text: '#e05a5a',
    border: 'rgba(204,31,46,0.35)',
    hdr: 'rgba(204,31,46,0.2)',
    cellNormal: 'rgba(204,31,46,0.09)',
    cellInDiv: 'rgba(204,31,46,0.2)',
  },
]

function divIdx(finish) {
  if (finish <= 4) return 0
  if (finish <= 8) return 1
  return 2
}

function ordinal(n) {
  const s = ['', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || 'th')
}

// ─── 14-week round-robin pattern ─────────────────────────────────────────────
// This is NNBE's published scheduling rule (see "How the schedule is built"
// below) and is also used as a fallback projection when the real schedule
// isn't in the database yet (season not drafted/synced from Sleeper).
// Teams indexed 0-11: [0-3] = Top, [4-7] = Mid, [8-11] = Bot.
// Each entry is one week's 6 matchup pairs.

const WEEK_PAIRS = [
  [[0,1],[2,3],[4,5],[6,7],[8,9],[10,11]],    // W1  in-div
  [[0,2],[1,3],[4,6],[5,7],[8,10],[9,11]],    // W2  in-div
  [[0,3],[1,2],[4,7],[5,6],[8,11],[9,10]],    // W3  in-div
  [[0,4],[1,5],[2,8],[3,9],[6,10],[7,11]],    // W4  cross
  [[0,5],[1,4],[2,9],[3,8],[6,11],[7,10]],    // W5  cross
  [[0,6],[1,7],[2,10],[3,11],[4,8],[5,9]],    // W6  cross
  [[0,7],[1,6],[2,11],[3,10],[4,9],[5,8]],    // W7  cross
  [[0,8],[1,9],[2,6],[3,7],[4,10],[5,11]],    // W8  cross
  [[0,9],[1,8],[2,7],[3,6],[4,11],[5,10]],    // W9  cross
  [[0,10],[1,11],[2,4],[3,5],[6,8],[7,9]],   // W10 cross
  [[0,11],[1,10],[2,5],[3,4],[6,9],[7,8]],   // W11 cross
  [[0,1],[2,3],[4,5],[6,7],[8,9],[10,11]],    // W12 in-div
  [[0,2],[1,3],[4,6],[5,7],[8,10],[9,11]],    // W13 in-div
  [[0,3],[1,2],[4,7],[5,6],[8,11],[9,10]],    // W14 in-div
]

const IN_DIV_WEEK = new Set([0, 1, 2, 11, 12, 13])  // 0-indexed

function buildProjectedSchedule(teams) {
  // Fallback only — returns oppByTeam[teamIdx][weekIdx] = opponentTeamIdx
  const opp = teams.map(() => Array(14).fill(-1))
  WEEK_PAIRS.forEach((pairs, wi) => {
    pairs.forEach(([a, b]) => {
      opp[a][wi] = b
      opp[b][wi] = a
    })
  })
  return opp
}

function buildRealSchedule(teams, schedule, weeks) {
  // Converts {ownerName: {week: opponentName}} into oppByTeam[teamIdx][weekIdx] = opponentTeamIdx
  const indexByOwner = {}
  teams.forEach((t, i) => { indexByOwner[t.owner] = i })
  return teams.map(team => {
    const weekMap = schedule[team.owner] ?? {}
    return Array.from({ length: weeks }, (_, wi) => {
      const oppName = weekMap[wi + 1]
      return oppName != null ? indexByOwner[oppName] : -1
    })
  })
}

// ─── How the schedule is built ────────────────────────────────────────────────

function HowScheduleWorks() {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: '16px', marginBottom: '8px' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-faint)', fontSize: '12px', fontWeight: 500,
          padding: '4px 0', marginBottom: open ? '14px' : 0,
        }}
      >
        <span style={{ fontSize: '11px', display: 'inline-block', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>▶</span>
        How the schedule is built
      </button>
      {open && (
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px', fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
          <p style={{ margin: '0 0 10px' }}>
            Each year, divisions are set by the <strong style={{ color: 'var(--text-primary)' }}>prior season's final standings</strong>:
            the top 4 finishers form the Top division, the next 4 the Mid division, and the bottom 4 the Bottom division.
          </p>
          <p style={{ margin: '0 0 10px' }}>
            <strong style={{ color: '#e3b341' }}>Weeks 1–3 &amp; 12–14</strong> are an in-division round robin — you play each
            division-mate, then play them again in weeks 12–14.
          </p>
          <p style={{ margin: 0 }}>
            <strong style={{ color: '#5b8dd9' }}>Weeks 4–11</strong> cover every team outside your division exactly once.
          </p>
        </div>
      )}
    </div>
  )
}

// ─── Division preview ─────────────────────────────────────────────────────────

function DivisionPreview({ teams, prevSeason, nextSeason }) {
  const divs = [teams.slice(0, 4), teams.slice(4, 8), teams.slice(8, 12)]

  return (
    <div style={{ marginBottom: '28px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '12px' }}>
        <p style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--text-faint)', margin: 0 }}>
          {nextSeason} Division Preview
        </p>
        <span style={{ fontSize: '11px', color: 'var(--text-faint)', fontStyle: 'italic' }}>
          based on {prevSeason} final standings
        </span>
      </div>

      <div className="schedule-divisions-grid">
        {divs.map((div, di) => {
          const d = DIV[di]
          return (
            <div key={di} style={{ background: 'var(--bg-surface)', border: `1px solid ${d.border}`, borderRadius: '10px', overflow: 'hidden' }}>
              <div style={{ padding: '8px 12px', background: d.hdr, borderBottom: `1px solid ${d.border}`, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase', color: d.text }}>{d.label}</span>
                <span style={{ fontSize: '11px', color: d.text, opacity: 0.65 }}>{d.range}</span>
              </div>
              {div.map((team, ti) => (
                <div key={ti} style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '7px 12px',
                  borderBottom: ti < div.length - 1 ? '1px solid var(--border)' : 'none',
                }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: d.text, width: '22px', flexShrink: 0 }}>{team.finish}.</span>
                  <span style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{team.owner}</span>
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Schedule grid ────────────────────────────────────────────────────────────

const WEEK_GROUPS = [
  { label: 'IN-DIVISION', span: 3, color: '#e3b341', bg: 'rgba(227,179,65,0.1)' },
  { label: 'CROSS-DIVISION', span: 8, color: '#5b8dd9', bg: 'rgba(26,58,107,0.1)' },
  { label: 'IN-DIVISION', span: 3, color: '#e3b341', bg: 'rgba(227,179,65,0.1)' },
]

// Column indices where a left-separator border should appear (W4 and W12)
const SEP_LEFT = new Set([3, 11])

function ScheduleGrid({ teams, oppByTeam, nextSeason, isProjected }) {
  const thBase = {
    padding: '5px 4px',
    fontSize: '11px',
    fontWeight: 700,
    textAlign: 'center',
    borderBottom: '1px solid var(--border)',
    minWidth: '58px',
  }

  return (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
        <p style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--text-faint)', margin: 0 }}>
          {nextSeason} Schedule
        </p>
        {isProjected && (
          <span style={{ background: 'rgba(227,179,65,0.12)', color: 'var(--gold)', border: '1px solid rgba(227,179,65,0.3)', borderRadius: '4px', padding: '2px 7px', fontSize: '11px', fontWeight: 600 }}>
            PROJECTED
          </span>
        )}
      </div>
      <p style={{ fontSize: '11px', color: 'var(--text-faint)', marginBottom: '14px' }}>
        {isProjected
          ? `Official ${nextSeason} schedule isn't published yet — showing the projected round-robin instead.`
          : `Official ${nextSeason} schedule, published by Sleeper.`}
      </p>

      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', minWidth: '960px', width: '100%' }}>
            <thead>
              {/* Group header */}
              <tr style={{ background: 'var(--bg-page)' }}>
                <th style={{ padding: '6px 12px', width: '120px' }} />
                {WEEK_GROUPS.map((g, gi) => (
                  <th
                    key={gi}
                    colSpan={g.span}
                    style={{
                      padding: '5px 0',
                      fontSize: '9px',
                      fontWeight: 700,
                      letterSpacing: '1.5px',
                      textTransform: 'uppercase',
                      textAlign: 'center',
                      color: g.color,
                      background: g.bg,
                      borderLeft: gi > 0 ? '2px solid var(--border-mid)' : 'none',
                    }}
                  >
                    {g.label}
                  </th>
                ))}
              </tr>
              {/* Week numbers */}
              <tr style={{ background: 'var(--bg-page)' }}>
                <th style={{ padding: '6px 12px', fontSize: '11px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                  Team
                </th>
                {Array.from({ length: 14 }, (_, wi) => (
                  <th
                    key={wi}
                    style={{
                      ...thBase,
                      color: IN_DIV_WEEK.has(wi) ? '#e3b341' : '#5b8dd9',
                      background: IN_DIV_WEEK.has(wi) ? 'rgba(227,179,65,0.08)' : 'rgba(26,58,107,0.08)',
                      borderLeft: SEP_LEFT.has(wi) ? '2px solid var(--border-mid)' : 'none',
                    }}
                  >
                    W{wi + 1}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {teams.map((team, ti) => {
                const di = divIdx(team.finish)
                const dc = DIV[di]
                const isDivBoundary = ti === 4 || ti === 8

                return (
                  <tr
                    key={ti}
                    className="standings-row"
                    style={{ borderTop: isDivBoundary ? '2px solid var(--border-mid)' : '1px solid var(--border)' }}
                  >
                    {/* Team label */}
                    <td style={{ padding: '7px 12px', whiteSpace: 'nowrap' }}>
                      <span style={{ fontSize: '11px', fontWeight: 700, color: dc.text, marginRight: '6px' }}>
                        {ordinal(team.finish)}
                      </span>
                      <span style={{ fontSize: '12px', color: 'var(--text-primary)' }}>
                        {team.owner}
                      </span>
                    </td>

                    {/* Opponent cells */}
                    {oppByTeam[ti].map((oppIdx, wi) => {
                      const opp = teams[oppIdx]
                      if (!opp) {
                        return (
                          <td key={wi} style={{ padding: '6px 4px', textAlign: 'center', fontSize: '11px', color: 'var(--text-faint)', fontStyle: 'italic', borderLeft: SEP_LEFT.has(wi) ? '2px solid var(--border-mid)' : 'none' }}>
                            —
                          </td>
                        )
                      }
                      const odi = divIdx(opp.finish)
                      const oc = DIV[odi]
                      const isInDiv = IN_DIV_WEEK.has(wi)
                      return (
                        <td
                          key={wi}
                          title={`Wk ${wi + 1}: vs ${opp.owner} (${ordinal(opp.finish)})`}
                          style={{
                            padding: '6px 4px',
                            textAlign: 'center',
                            fontSize: '11px',
                            fontWeight: 500,
                            color: oc.text,
                            background: isInDiv ? oc.cellInDiv : oc.cellNormal,
                            whiteSpace: 'nowrap',
                            borderLeft: SEP_LEFT.has(wi) ? '2px solid var(--border-mid)' : 'none',
                          }}
                        >
                          {opp.owner}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Legend */}
        <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)', display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          {DIV.map((d, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: d.cellInDiv, border: `1px solid ${d.border}` }} />
              <span style={{ fontSize: '11px', color: 'var(--text-faint)' }}>{d.label} opponent</span>
            </div>
          ))}
          <span style={{ fontSize: '11px', color: 'var(--text-faint)', marginLeft: 'auto', fontStyle: 'italic' }}>
            Darker shade = in-division week
          </span>
        </div>
      </div>
    </div>
  )
}

// ─── Page root ────────────────────────────────────────────────────────────────

export default function Schedule({ embedded }) {
  const { data: seasonsData } = useQuery({
    queryKey: ['history-seasons-complete'],
    queryFn: () => fetch('/api/history/seasons/complete').then(r => r.json()),
  })

  const prevSeason = seasonsData?.seasons?.[0]
  const nextSeason = (prevSeason ?? 2025) + 1

  const { data: finishData, isLoading } = useQuery({
    queryKey: ['finish-order', prevSeason],
    queryFn: () => fetch(`/api/history/finish-order/${prevSeason}`).then(r => r.json()),
    enabled: !!prevSeason,
  })

  const { data: scheduleData, isLoading: loadingSchedule } = useQuery({
    queryKey: ['real-schedule', nextSeason],
    queryFn: () => fetch(`/api/history/schedule/${nextSeason}`).then(r => r.json()),
    enabled: !!prevSeason,
  })

  const teams = finishData?.teams ?? []

  if (isLoading || loadingSchedule || (!finishData && prevSeason)) {
    return (
      <div style={{ padding: '40px 0', display: 'flex', justifyContent: 'center' }}>
        <LoadingSpinner />
      </div>
    )
  }

  if (teams.length === 0) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center' }}>
        <p style={{ fontSize: '13px', color: 'var(--text-faint)' }}>No standings data available yet.</p>
      </div>
    )
  }

  const realSchedule = scheduleData?.schedule ?? {}
  const hasRealSchedule = Object.keys(realSchedule).length > 0
  const oppByTeam = hasRealSchedule
    ? buildRealSchedule(teams, realSchedule, scheduleData.weeks || 14)
    : buildProjectedSchedule(teams)

  return (
    <div style={embedded ? {} : { maxWidth: '1280px', margin: '0 auto', padding: '24px clamp(12px, 3vw, 24px)' }}>
      {!embedded && (
        <>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '28px', letterSpacing: '2px', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Schedule
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '24px' }}>
            {hasRealSchedule
              ? `${nextSeason} matchup schedule, as published by Sleeper.`
              : `Projected ${nextSeason} matchup schedule based on ${prevSeason} final standings.`}
          </p>
        </>
      )}

      <DivisionPreview teams={teams} prevSeason={prevSeason} nextSeason={nextSeason} />
      <ScheduleGrid teams={teams} oppByTeam={oppByTeam} nextSeason={nextSeason} isProjected={!hasRealSchedule} />
      <HowScheduleWorks />
    </div>
  )
}
