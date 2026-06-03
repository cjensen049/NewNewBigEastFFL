/**
 * InSeason.jsx — Playoff Picture, Race to the Bottom, and Schedule Luck.
 *
 * Tabs:
 *   Standings    — two-panel view: playoff picture (left) + race to bottom (right)
 *   Luck         — By Season / All-Time schedule luck analysis
 *   Race History — RTB season-by-season grid
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell, ReferenceLine, ResponsiveContainer,
} from 'recharts'

import { TabBar, TabPanel } from '../components/Tabs'
import DataTable from '../components/DataTable'
import LoadingSpinner from '../components/LoadingSpinner'

const TABS = [
  { id: 'standings',    label: 'Standings' },
  { id: 'luck',         label: 'Schedule Luck' },
  { id: 'racehistory',  label: 'Race History' },
]

// ─── Shared helpers ───────────────────────────────────────────────────────────

const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

function verdictColor(v) {
  if (!v) return 'var(--text-muted)'
  const l = v.toLowerCase()
  if (l.includes('unlucky')) return 'var(--brand-red)'
  if (l.includes('lucky'))   return 'var(--green)'
  return 'var(--gold)'
}

function luckVerdictFromDiff(diff) {
  if (diff == null) return null
  if (diff >= 1.5)  return 'Very Lucky'
  if (diff >= 0.5)  return 'Lucky'
  if (diff >= -0.5) return 'Average'
  if (diff >= -1.5) return 'Unlucky'
  return 'Very Unlucky'
}

function wlStyle(wins, losses) {
  if (wins > losses)  return { background: 'rgba(63,185,80,0.12)',  color: 'var(--green)' }
  if (losses > wins)  return { background: 'rgba(204,31,46,0.1)',   color: 'var(--brand-red)' }
  return               { background: 'rgba(227,179,65,0.12)', color: 'var(--gold)' }
}

function luckRowClass(diff) {
  if (diff >= 1.5)  return 'bg-green-900/30'
  if (diff >= 0.5)  return 'bg-green-900/15'
  if (diff <= -1.5) return 'bg-red-900/30'
  if (diff <= -0.5) return 'bg-red-900/15'
  return ''
}

const SeasonSelect = ({ seasons, value, onChange }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
    <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-faint)' }}>Season</span>
    <select
      value={value ?? ''}
      onChange={e => onChange(Number(e.target.value))}
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-mid)', borderRadius: '6px', padding: '5px 10px', fontSize: '13px', color: 'var(--text-primary)', fontFamily: 'var(--font-body)', outline: 'none' }}
    >
      {seasons.map(s => <option key={s} value={s}>{s}</option>)}
    </select>
  </div>
)

// ─── Playoff Picture panel ────────────────────────────────────────────────────

const ZONES = [
  { start: 0, end: 4,  label: '🏆 Playoff',   color: 'var(--green)',     bg: 'rgba(63,185,80,0.06)',  border: 'rgba(63,185,80,0.25)' },
  { start: 4, end: 6,  label: '🎯 Wild Card',  color: 'var(--gold)',      bg: 'rgba(227,179,65,0.06)', border: 'rgba(227,179,65,0.3)' },
  { start: 6, end: 12, label: '✗ Eliminated',  color: 'var(--brand-red)', bg: 'rgba(204,31,46,0.04)', border: 'rgba(204,31,46,0.2)' },
]

function getZone(pos) {
  return ZONES.find(z => pos >= z.start && pos < z.end) ?? ZONES[2]
}

function PlayoffPicture({ rows, nextWeek }) {
  if (!rows || rows.length === 0) {
    return <p style={{ color: 'var(--text-faint)', fontSize: '13px', fontStyle: 'italic', padding: '16px' }}>No in-season data yet.</p>
  }

  // PTS BACK — everyone is measured against 1st place
  const leader = rows[0]?.pts_for ?? 0

  const TH = ({ children, align = 'left' }) => (
    <th style={{ padding: '8px 10px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', textAlign: align, whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>
      {children}
    </th>
  )

  const oppHeader = nextWeek ? `Wk ${nextWeek}` : 'Next'

  let lastZone = null
  const tableRows = []
  rows.forEach((r, i) => {
    const zone = getZone(i)

    // Insert zone divider row when entering a new zone
    if (zone !== lastZone) {
      lastZone = zone
      tableRows.push({ _divider: true, zone, key: `div-${i}` })
    }

    const ptsBack = i === 0 ? null : (leader - (r.pts_for ?? 0))
    const wl = wlStyle(r.actual_wins, r.actual_losses)
    const simWl = wlStyle(r.sim_wins, r.sim_losses)
    const winPctDiff = (r.actual_win_pct ?? 0) - (r.sim_win_pct ?? 0)
    const verdict = luckVerdictFromDiff(r.luck_diff)
    tableRows.push({ _divider: false, r, i, zone, ptsBack, wl, simWl, winPctDiff, verdict, key: `row-${i}` })
  })

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Playoff Picture</span>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', minWidth: '480px' }}>
          <thead>
            <tr>
              <TH>Owner</TH>
              <TH align="right">W-L</TH>
              <TH align="right">Pts</TH>
              <TH align="right">Back</TH>
              <TH align="right">Sim</TH>
              <TH align="right">Diff</TH>
              <TH align="right">Verdict</TH>
              <TH>{oppHeader}</TH>
            </tr>
          </thead>
          <tbody>
            {tableRows.map(item => {
              if (item._divider) {
                return (
                  <tr key={item.key}>
                    <td colSpan={8} style={{ padding: '6px 10px', background: item.zone.bg, borderTop: `2px solid ${item.zone.border}`, borderBottom: `1px solid ${item.zone.border}` }}>
                      <span style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: item.zone.color }}>
                        {item.zone.label}
                      </span>
                    </td>
                  </tr>
                )
              }
              const { r, i, zone, ptsBack, wl, simWl, winPctDiff, verdict } = item
              const pts = r.pts_for != null ? Number(r.pts_for).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—'
              const backStr = ptsBack != null ? ptsBack.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—'
              const diffStr = `${winPctDiff >= 0 ? '+' : ''}${(winPctDiff * 100).toFixed(1)}%`
              return (
                <tr key={item.key} className="standings-row" style={{ borderBottom: '1px solid var(--border)', background: zone.bg }}>
                  <td style={{ padding: '8px 10px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{r.owner}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span style={{ ...wl, borderRadius: '4px', padding: '2px 5px', fontSize: '11px', fontWeight: 600 }}>
                      {r.actual_wins}-{r.actual_losses}
                    </span>
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{pts}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-faint)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{backStr}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span style={{ ...simWl, borderRadius: '4px', padding: '2px 5px', fontSize: '11px', fontWeight: 600 }}>
                      {r.sim_wins}-{r.sim_losses}
                    </span>
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, whiteSpace: 'nowrap', color: winPctDiff > 0 ? 'var(--green)' : winPctDiff < 0 ? 'var(--brand-red)' : 'var(--text-muted)' }}>
                    {diffStr}
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap', color: verdictColor(verdict), fontWeight: 500, fontSize: '11px' }}>
                    {verdict ?? '—'}
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {r.next_opponent ?? <span style={{ color: 'var(--text-faint)' }}>—</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Race to the Bottom panel ─────────────────────────────────────────────────

function RTBPanel({ rows }) {
  if (!rows || rows.length === 0) {
    return (
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: '8px' }}>Race to the Bottom</span>
        <p style={{ fontSize: '13px', color: 'var(--text-faint)', fontStyle: 'italic' }}>No data yet — check back after the regular season ends.</p>
      </div>
    )
  }

  // rows sorted by draft_pick ASC (1 = best pick = lowest optimal pts)
  const basePts = rows[0]?.optimal_pts ?? 0

  const TH = ({ children, align = 'left' }) => (
    <th style={{ padding: '7px 10px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', textAlign: align, whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>
      {children}
    </th>
  )

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Race to the Bottom</span>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
          <thead>
            <tr>
              <TH>#</TH>
              <TH>Owner</TH>
              <TH align="right">W-L</TH>
              <TH align="right">Opt PF</TH>
              <TH align="right">Back</TH>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const wl = wlStyle(r.wins, r.losses)
              const optPts = r.optimal_pts != null ? Number(r.optimal_pts).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—'
              const back = r.optimal_pts != null ? (r.optimal_pts - basePts).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—'
              return (
                <tr key={i} className="standings-row" style={{ borderBottom: '1px solid var(--border)', background: 'rgba(204,31,46,0.04)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 700, fontSize: '11px' }}>
                    <span style={{ background: 'rgba(204,31,46,0.15)', color: 'var(--brand-red)', borderRadius: '4px', padding: '2px 6px' }}>
                      #{r.draft_pick}
                    </span>
                  </td>
                  <td style={{ padding: '8px 10px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{r.owner}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span style={{ ...wl, borderRadius: '4px', padding: '2px 5px', fontSize: '11px', fontWeight: 600 }}>
                      {r.wins}-{r.losses}
                    </span>
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{optPts}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', color: i === 0 ? 'var(--brand-red)' : 'var(--text-faint)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', fontWeight: i === 0 ? 600 : 400 }}>
                    {i === 0 ? 'Leader' : `+${back}`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
        <p style={{ fontSize: '10px', color: 'var(--text-faint)', margin: 0 }}>Ranked by lowest optimal PF — weakest roster earns the 1st rookie draft pick</p>
      </div>
    </div>
  )
}

// ─── Standings tab ────────────────────────────────────────────────────────────

function StandingsTab() {
  const { data: seasonsData, isLoading: loadSeasons } = useQuery({
    queryKey: ['inseason-seasons'],
    queryFn: () => fetch('/api/in-season/seasons').then(r => r.json()),
  })

  const [selectedSeason, setSelectedSeason] = useState(null)
  const seasons = seasonsData?.seasons ?? []
  const activeSeason = selectedSeason ?? seasons[0]

  const { data: snapshotData, isLoading: loadSnap } = useQuery({
    queryKey: ['inseason-snapshot', activeSeason],
    queryFn: () => fetch(`/api/in-season/snapshot/${activeSeason}`).then(r => r.json()),
    enabled: !!activeSeason,
  })

  const { data: rtbData, isLoading: loadRTB } = useQuery({
    queryKey: ['rtb-season', activeSeason],
    queryFn: () => fetch(`/api/in-season/rtb/${activeSeason}`).then(r => r.json()),
    enabled: !!activeSeason,
  })

  if (loadSeasons) return <LoadingSpinner />

  return (
    <div>
      {seasons.length > 1 && (
        <SeasonSelect seasons={seasons} value={activeSeason} onChange={setSelectedSeason} />
      )}

      {(loadSnap || loadRTB) ? <LoadingSpinner /> : (
        <div className="inseason-main-grid">
          <PlayoffPicture rows={snapshotData?.rows ?? []} nextWeek={snapshotData?.next_week} />
          <RTBPanel rows={rtbData?.rows ?? []} />
        </div>
      )}
    </div>
  )
}

// ─── Schedule Luck tab ────────────────────────────────────────────────────────

function LuckTab() {
  const { data: seasonsData, isLoading: loadSeasons } = useQuery({
    queryKey: ['inseason-seasons'],
    queryFn: () => fetch('/api/in-season/seasons').then(r => r.json()),
  })

  const [selectedSeason, setSelectedSeason] = useState(null)
  const [subTab, setSubTab] = useState('season')

  const seasons = seasonsData?.seasons ?? []
  const activeSeason = selectedSeason ?? seasons[0]

  const { data: seasonData, isLoading: loadSeason } = useQuery({
    queryKey: ['luck-season', activeSeason],
    queryFn: () => fetch(`/api/in-season/luck/${activeSeason}`).then(r => r.json()),
    enabled: !!activeSeason,
  })

  const { data: allTimeData, isLoading: loadAllTime } = useQuery({
    queryKey: ['luck-alltime'],
    queryFn: () => fetch('/api/in-season/luck/all-time').then(r => r.json()),
  })

  if (loadSeasons) return <LoadingSpinner />

  const seasonRows = (seasonData?.rows ?? []).map(r => ({
    ...r,
    actual_pct_fmt: pct(r.actual_win_pct),
    sim_pct_fmt:    pct(r.sim_win_pct),
    diff_fmt:       `${(r.win_pct_diff >= 0 ? '+' : '')}${pct(r.win_pct_diff)}`,
    actual_record:  `${r.actual_wins}-${r.actual_losses}`,
    sim_record:     `${r.sim_wins}-${r.sim_losses}`,
  }))

  const seasonChartData = seasonRows.map(r => ({
    name: r.owner,
    diff: parseFloat((r.win_pct_diff * 100).toFixed(1)),
    luck_diff: r.luck_diff,
  }))

  const allTimeRows = (allTimeData?.rows ?? []).map(r => ({
    ...r,
    actual_pct_fmt: pct(r.actual_win_pct),
    sim_pct_fmt:    pct(r.sim_win_pct),
    diff_fmt:       `${(r.win_pct_diff >= 0 ? '+' : '')}${pct(r.win_pct_diff)}`,
  }))

  const allTimeChartData = allTimeRows.map(r => ({
    name: r.owner,
    diff: parseFloat((r.win_pct_diff * 100).toFixed(1)),
    total_luck: r.total_luck,
  }))

  return (
    <div>
      <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px', lineHeight: 1.6 }}>
        Compares each team's actual record against a simulated record if they had played every other
        team each week. Positive = lucky schedule, negative = unlucky.
      </p>

      {/* Sub-tab: By Season / All-Time */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        {[['season', 'By Season'], ['alltime', 'All-Time']].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setSubTab(id)}
            style={{
              padding: '6px 16px',
              fontSize: '13px',
              borderRadius: '6px',
              border: subTab === id ? '1px solid transparent' : '1px solid var(--border-mid)',
              background: subTab === id ? 'var(--brand-navy)' : 'var(--border)',
              color: subTab === id ? '#ffffff' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'background 0.15s, color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {subTab === 'season' && (
        <div>
          <SeasonSelect seasons={seasons} value={activeSeason} onChange={setSelectedSeason} />
          {loadSeason ? <LoadingSpinner /> : (
            <>
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', marginBottom: '24px' }}>
                <div style={{ overflowX: 'auto', maxHeight: '460px', overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead className="sticky top-0">
                      <tr>
                        {['Owner', 'Actual W-L', 'Actual Win%', 'Sim W-L', 'Sim Win%', 'Diff', 'Verdict'].map((h, hi) => (
                          <th key={h} style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', textAlign: hi === 0 ? 'left' : 'right', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {seasonRows.map((r, i) => (
                        <tr key={i} className={`luck-table-row ${luckRowClass(r.luck_diff)}`} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '9px 12px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{r.owner}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{r.actual_record}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{r.actual_pct_fmt}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{r.sim_record}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{r.sim_pct_fmt}</td>
                          <td style={{ padding: '9px 12px', fontWeight: 600, textAlign: 'right', whiteSpace: 'nowrap', color: r.win_pct_diff > 0 ? 'var(--green)' : r.win_pct_diff < 0 ? 'var(--brand-red)' : 'var(--text-muted)' }}>{r.diff_fmt}</td>
                          <td style={{ padding: '9px 12px', fontWeight: 500, textAlign: 'right', whiteSpace: 'nowrap', color: verdictColor(r.verdict) }}>{r.verdict}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>{activeSeason} Schedule Luck (Actual Win% − Sim Win%)</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={seasonChartData} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--text-faint)" tick={{ fontSize: 11 }} />
                  <YAxis stroke="var(--text-faint)" tick={{ fontSize: 11 }} tickFormatter={v => `${v}%`} />
                  <ReferenceLine y={0} stroke="var(--text-muted)" strokeWidth={1} />
                  <Tooltip
                    formatter={v => [`${v}%`, 'Win% Diff']}
                    contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '6px' }}
                  />
                  <Bar dataKey="diff" label={{ position: 'top', fill: 'var(--text-faint)', fontSize: 10 }}>
                    {seasonChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.luck_diff > 0.5 ? '#3fb950' : entry.luck_diff < -0.5 ? '#cc1f2e' : '#4a6380'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      )}

      {subTab === 'alltime' && (
        <div>
          {loadAllTime ? <LoadingSpinner /> : (
            <>
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', marginBottom: '24px' }}>
                <div style={{ overflowX: 'auto', maxHeight: '460px', overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead className="sticky top-0">
                      <tr>
                        {['Owner', 'Actual W-L', 'Actual Win%', 'Sim W-L', 'Sim Win%', 'Diff', 'Verdict'].map((h, hi) => (
                          <th key={h} style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', textAlign: hi === 0 ? 'left' : 'right', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {allTimeRows.map((r, i) => (
                        <tr key={i} className={`luck-table-row ${luckRowClass(r.total_luck)}`} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '9px 12px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{r.owner}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{r.actual_record}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{r.actual_pct_fmt}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{r.sim_record}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', textAlign: 'right', whiteSpace: 'nowrap' }}>{r.sim_pct_fmt}</td>
                          <td style={{ padding: '9px 12px', fontWeight: 600, textAlign: 'right', whiteSpace: 'nowrap', color: r.win_pct_diff > 0 ? 'var(--green)' : r.win_pct_diff < 0 ? 'var(--brand-red)' : 'var(--text-muted)' }}>{r.diff_fmt}</td>
                          <td style={{ padding: '9px 12px', fontWeight: 500, textAlign: 'right', whiteSpace: 'nowrap', color: verdictColor(r.verdict) }}>{r.verdict}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>All-Time Schedule Luck (Actual Win% − Sim Win%)</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={allTimeChartData} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--text-faint)" tick={{ fontSize: 11 }} />
                  <YAxis stroke="var(--text-faint)" tick={{ fontSize: 11 }} tickFormatter={v => `${v}%`} />
                  <ReferenceLine y={0} stroke="var(--text-muted)" strokeWidth={1} />
                  <Tooltip
                    formatter={v => [`${v}%`, 'Win% Diff']}
                    contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '6px' }}
                  />
                  <Bar dataKey="diff">
                    {allTimeChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.total_luck > 0 ? '#3fb950' : '#cc1f2e'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Race History tab ─────────────────────────────────────────────────────────

function RaceHistoryTab() {
  const { data: histData, isLoading: loadHist } = useQuery({
    queryKey: ['rtb-history'],
    queryFn: () => fetch('/api/in-season/rtb/history').then(r => r.json()),
  })

  if (loadHist) return <LoadingSpinner />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <p style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '12px' }}>Summary</p>
        <DataTable
          rows={histData?.summary ?? []}
          maxHeight="400px"
          columns={[
            { key: 'owner',       label: 'Owner' },
            { key: 'appearances', label: 'Appearances', align: 'right' },
            { key: 'best_pick',   label: 'Best Pick',   align: 'right' },
            { key: 'avg_pick',    label: 'Avg Pick',    align: 'right' },
            { key: 'seasons',     label: 'Seasons' },
          ]}
        />
      </div>

      <div>
        <p style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '12px' }}>Draft Pick by Season</p>
        <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: '8px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr>
                <th style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', textAlign: 'left', whiteSpace: 'nowrap', position: 'sticky', left: 0, borderBottom: '1px solid var(--border)' }}>Owner</th>
                {(histData?.seasons ?? []).map(s => (
                  <th key={s} style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', textAlign: 'right', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>{s}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(histData?.owner_grid ?? []).map((row, i) => (
                <tr key={i} className="standings-row" style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', position: 'sticky', left: 0, background: 'var(--bg-surface)' }}>{row.owner}</td>
                  {(histData?.seasons ?? []).map(s => (
                    <td key={s} style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{row[s] ?? '—'}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ─── Page assembly ────────────────────────────────────────────────────────────

export default function InSeason({ embedded = false }) {
  const [tab, setTab] = useState('standings')

  return (
    <div>
      {!embedded && (
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '28px', letterSpacing: '2px', marginBottom: '24px' }}>In-Season</h1>
      )}
      <TabBar tabs={TABS} activeTab={tab} onChange={setTab} />
      <TabPanel id="standings"   activeTab={tab}><StandingsTab /></TabPanel>
      <TabPanel id="luck"        activeTab={tab}><LuckTab /></TabPanel>
      <TabPanel id="racehistory" activeTab={tab}><RaceHistoryTab /></TabPanel>
    </div>
  )
}
