/**
 * InSeason.jsx — Luck-o-Meter and Race to the Bottom page.
 *
 * Tabs: Luck-o-Meter | Race to the Bottom
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
  { id: 'luck', label: 'Luck-o-Meter' },
  { id: 'rtb',  label: 'Race to the Bottom' },
]

// Row background color based on luck diff value
function luckRowClass(diff) {
  if (diff >= 1.5)  return 'bg-green-900/30'
  if (diff >= 0.5)  return 'bg-green-900/15'
  if (diff <= -1.5) return 'bg-red-900/30'
  if (diff <= -0.5) return 'bg-red-900/15'
  return ''
}

const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—'

function verdictColor(v) {
  if (!v) return 'var(--text-muted)'
  const l = v.toLowerCase()
  if (l.includes('unlucky')) return 'var(--brand-red)'
  if (l.includes('lucky'))   return 'var(--green)'
  return 'var(--gold)'
}

// ---------------------------------------------------------------------------
// Luck-o-Meter tab
// ---------------------------------------------------------------------------

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

  // Season tab content
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

  // All-time tab content
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
      <p className="text-sm text-gray-400 mb-4">
        Compares each team's actual record against a simulated record if they had played every other
        team each week. Positive = lucky schedule, negative = unlucky.
      </p>

      {/* Sub-tab: By Season / All-Time */}
      <div className="flex gap-2 mb-6">
        {['season', 'alltime'].map((id, i) => (
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
            {i === 0 ? 'By Season' : 'All-Time'}
          </button>
        ))}
      </div>

      {subTab === 'season' && (
        <div>
          {/* Season selector */}
          <div className="flex items-center gap-3 mb-5">
            <label className="text-sm text-gray-400">Season:</label>
            <select
              value={activeSeason ?? ''}
              onChange={e => setSelectedSeason(Number(e.target.value))}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
            >
              {seasons.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {loadSeason ? <LoadingSpinner /> : (
            <>
              {/* Luck table with color-coded rows */}
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', marginBottom: '24px' }}>
                <div style={{ overflowX: 'auto', maxHeight: '460px', overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead className="sticky top-0">
                      <tr>
                        {['Owner', 'Actual W-L', 'Actual Win%', 'Sim W-L', 'Sim Win%', 'Diff', 'Verdict'].map((h, hi) => (
                          <th key={h} style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', textAlign: hi === 0 ? 'left' : 'right', whiteSpace: 'nowrap' }}>
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

              {/* Luck bar chart */}
              <h3 className="text-sm font-semibold mb-3">{activeSeason} Schedule Luck (Actual Win% − Sim Win%)</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={seasonChartData} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                  <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} tickFormatter={v => `${v}%`} />
                  <ReferenceLine y={0} stroke="#ffffff" strokeWidth={1} />
                  <Tooltip
                    formatter={v => [`${v}%`, 'Win% Diff']}
                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '6px' }}
                  />
                  <Bar dataKey="diff" label={{ position: 'top', fill: '#9CA3AF', fontSize: 10 }}>
                    {seasonChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.luck_diff > 0.5 ? '#2ecc71' : entry.luck_diff < -0.5 ? '#e74c3c' : '#95a5a6'} />
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
                          <th key={h} style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', textAlign: hi === 0 ? 'left' : 'right', whiteSpace: 'nowrap' }}>
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

              <h3 className="text-sm font-semibold mb-3">All-Time Schedule Luck (Actual Win% − Sim Win%)</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={allTimeChartData} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                  <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} tickFormatter={v => `${v}%`} />
                  <ReferenceLine y={0} stroke="#ffffff" strokeWidth={1} />
                  <Tooltip
                    formatter={v => [`${v}%`, 'Win% Diff']}
                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '6px' }}
                  />
                  <Bar dataKey="diff">
                    {allTimeChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.total_luck > 0 ? '#2ecc71' : '#e74c3c'} />
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

// ---------------------------------------------------------------------------
// Race to the Bottom tab
// ---------------------------------------------------------------------------

function RTBTab() {
  const { data: seasonsData } = useQuery({
    queryKey: ['inseason-seasons'],
    queryFn: () => fetch('/api/in-season/seasons').then(r => r.json()),
  })

  const [selectedSeason, setSelectedSeason] = useState(null)
  const [subTab, setSubTab] = useState('season')

  const seasons = seasonsData?.seasons ?? []
  const activeSeason = selectedSeason ?? seasons[0]

  const { data: seasonData, isLoading: loadSeason } = useQuery({
    queryKey: ['rtb-season', activeSeason],
    queryFn: () => fetch(`/api/in-season/rtb/${activeSeason}`).then(r => r.json()),
    enabled: !!activeSeason,
  })

  const { data: histData, isLoading: loadHist } = useQuery({
    queryKey: ['rtb-history'],
    queryFn: () => fetch('/api/in-season/rtb/history').then(r => r.json()),
  })

  const rtbRows = (seasonData?.rows ?? []).map(r => ({
    pick: `#${r.draft_pick}`,
    owner: r.owner,
    record: `${r.wins}-${r.losses}`,
    optimal_pts: r.optimal_pts?.toFixed(1) ?? '—',
    actual_pts: r.actual_pts?.toFixed(1) ?? '—',
    lineup_pct: r.lineup_pct != null ? `${r.lineup_pct.toFixed(1)}%` : '—',
  }))

  const chartData = (seasonData?.rows ?? []).map((r, i) => ({
    name: r.owner,
    'Optimal PF': r.optimal_pts,
    pick: `#${r.draft_pick}`,
    colorIdx: i,
  }))

  const COLORS = ['#e74c3c', '#f39c12', '#f1c40f', '#95a5a6', '#95a5a6', '#95a5a6']

  return (
    <div>
      <p className="text-sm text-gray-400 mb-4">
        Non-playoff teams ranked by Sleeper's optimal PF — the maximum score achievable with the
        best possible lineup each week. Lowest optimal PF earns the 1st rookie draft pick,
        rewarding the weakest roster rather than rewarding tanking.
      </p>

      <div className="flex gap-2 mb-6">
        {['season', 'history'].map((id, i) => (
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
            {i === 0 ? 'By Season' : 'History'}
          </button>
        ))}
      </div>

      {subTab === 'season' && (
        <div>
          <div className="flex items-center gap-3 mb-5">
            <label className="text-sm text-gray-400">Season:</label>
            <select
              value={activeSeason ?? ''}
              onChange={e => setSelectedSeason(Number(e.target.value))}
              className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
            >
              {seasons.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {loadSeason ? <LoadingSpinner /> : (
            <>
              <DataTable
                rows={rtbRows}
                maxHeight="300px"
                columns={[
                  { key: 'pick',        label: 'Pick' },
                  { key: 'owner',       label: 'Owner' },
                  { key: 'record',      label: 'W-L' },
                  { key: 'optimal_pts', label: 'Optimal PF', align: 'right' },
                  { key: 'actual_pts',  label: 'Actual PF',  align: 'right' },
                  { key: 'lineup_pct',  label: 'Lineup %',   align: 'right' },
                ]}
              />
              <h3 className="text-sm font-semibold mt-6 mb-3">{activeSeason} — Optimal PF</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 20, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                  <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} />
                  <Tooltip
                    formatter={(v, _, props) => [v.toFixed(1), 'Optimal PF']}
                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '6px' }}
                  />
                  <Bar dataKey="Optimal PF" label={{ position: 'top', fill: '#9CA3AF', fontSize: 10 }}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={COLORS[Math.min(i, COLORS.length - 1)]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      )}

      {subTab === 'history' && (
        <div className="space-y-6">
          {loadHist ? <LoadingSpinner /> : (
            <>
              <div>
                <h2 className="text-lg font-semibold mb-3">Summary</h2>
                <DataTable
                  rows={histData?.summary ?? []}
                  maxHeight="460px"
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
                <h2 className="text-lg font-semibold mb-3">Draft Pick by Season</h2>
                <div className="overflow-x-auto rounded border border-gray-700">
                  <table className="text-sm text-gray-300">
                    <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                      <tr>
                        <th className="px-3 py-2 sticky left-0 bg-gray-800">Owner</th>
                        {(histData?.seasons ?? []).map(s => (
                          <th key={s} className="px-3 py-2 text-right whitespace-nowrap">{s}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700/50">
                      {(histData?.owner_grid ?? []).map((row, i) => (
                        <tr key={i} className="hover:bg-gray-700/20">
                          <td className="px-3 py-2 sticky left-0 bg-gray-900 font-medium">{row.owner}</td>
                          {(histData?.seasons ?? []).map(s => (
                            <td key={s} className="px-3 py-2 text-right text-gray-400">{row[s] ?? '—'}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page assembly
// ---------------------------------------------------------------------------

export default function InSeason({ embedded = false }) {
  const [tab, setTab] = useState('luck')

  return (
    <div>
      {!embedded && <h1 className="text-2xl font-bold mb-6">In-Season</h1>}
      <TabBar tabs={TABS} activeTab={tab} onChange={setTab} />
      <TabPanel id="luck" activeTab={tab}><LuckTab /></TabPanel>
      <TabPanel id="rtb"  activeTab={tab}><RTBTab /></TabPanel>
    </div>
  )
}
