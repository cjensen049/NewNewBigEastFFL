/**
 * InSeason.jsx — Playoff Picture + Race to the Bottom.
 *
 * Single-view page: season selector → Playoff Picture (full width) →
 * Race to the Bottom (eliminated teams only, stacked below).
 */
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '../components/LoadingSpinner'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function wlStyle(wins, losses) {
  if (wins > losses)  return { background: 'rgba(63,185,80,0.12)',  color: 'var(--green)' }
  if (losses > wins)  return { background: 'rgba(204,31,46,0.1)',   color: 'var(--brand-red)' }
  return               { background: 'rgba(227,179,65,0.12)', color: 'var(--gold)' }
}

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

// Formats a numeric delta with + prefix and green/red color.
// null → "—" in faint. 0 → "0.0" in muted.
function formatDelta(val) {
  if (val == null) return { text: '—', color: 'var(--text-faint)' }
  if (val === 0)   return { text: '0.0', color: 'var(--text-muted)' }
  const abs = Math.abs(val).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  return val > 0
    ? { text: `+${abs}`, color: 'var(--green)' }
    : { text: `-${abs}`, color: 'var(--brand-red)' }
}

const ZONES = [
  { id: 'playoff',    label: '🏆 Playoff',   color: 'var(--green)',     bg: 'rgba(63,185,80,0.06)',  border: 'rgba(63,185,80,0.25)' },
  { id: 'wildcard',   label: '🎯 Wild Card',  color: 'var(--gold)',      bg: 'rgba(227,179,65,0.06)', border: 'rgba(227,179,65,0.3)' },
  { id: 'eliminated', label: '✗ Eliminated',  color: 'var(--brand-red)', bg: 'rgba(204,31,46,0.04)', border: 'rgba(204,31,46,0.2)' },
]
const ZONE_MAP = Object.fromEntries(ZONES.map(z => [z.id, z]))

// Sortable <th> cell used by both tables
function SortTH({ colKey, activeKey, dir, onSort, children, align = 'left' }) {
  const active = activeKey === colKey
  return (
    <th onClick={() => onSort(colKey)} style={{
      padding: '8px 10px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px',
      textTransform: 'uppercase', background: 'var(--bg-page)', whiteSpace: 'nowrap',
      borderBottom: '1px solid var(--border)', textAlign: align,
      cursor: 'pointer', userSelect: 'none',
      color: active ? 'var(--text-primary)' : 'var(--text-faint)',
    }}>
      {children}
      <span style={{ marginLeft: '4px', opacity: active ? 1 : 0.45, fontSize: '9px' }}>
        {active ? (dir === 'asc' ? '↑' : '↓') : '↕'}
      </span>
    </th>
  )
}

function useSort(defaultDir = 'desc') {
  const [sortKey, setSortKey] = useState(null)
  const [sortDir, setSortDir] = useState(defaultDir)
  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir(defaultDir) }
  }
  return { sortKey, sortDir, handleSort, reset: () => setSortKey(null) }
}

function applySort(rows, key, dir) {
  if (!key) return rows
  return [...rows].sort((a, b) => {
    const av = a[key], bv = b[key]
    const an = parseFloat(av), bn = parseFloat(bv)
    const cmp = !isNaN(an) && !isNaN(bn) ? an - bn : String(av ?? '').localeCompare(String(bv ?? ''))
    return dir === 'asc' ? cmp : -cmp
  })
}

// ─── Playoff Picture ──────────────────────────────────────────────────────────

function PlayoffPicture({ zoneRows, nextWeek, finishEmoji = {} }) {
  const { sortKey, sortDir, handleSort, reset } = useSort('desc')

  // Reference points for BACK column:
  //   refWC   = 5th-place pts_for (Wild Card leader — reference for positions 1–6)
  //   refElim = 6th-place pts_for (last Wild Card spot — reference for positions 7–12)
  const refWC   = zoneRows[4]?.pts_for ?? null
  const refElim = zoneRows[5]?.pts_for ?? null

  const enriched = useMemo(() => zoneRows.map(r => {
    let back = null
    if (r._pos === 4)                         back = null
    else if (r._pos < 6 && refWC != null)     back = (r.pts_for ?? 0) - refWC
    else if (r._pos >= 6 && refElim != null)  back = (r.pts_for ?? 0) - refElim
    return {
      ...r,
      _back: back,
      _winPctDiff: (r.actual_win_pct ?? 0) - (r.sim_win_pct ?? 0),
    }
  }), [zoneRows, refWC, refElim])

  const displayRows = useMemo(() => applySort(enriched, sortKey, sortDir), [enriched, sortKey, sortDir])
  const isSorted = !!sortKey
  const oppHeader = nextWeek ? `Wk ${nextWeek}` : 'Next'

  if (zoneRows.length === 0) {
    return <p style={{ color: 'var(--text-faint)', fontSize: '13px', fontStyle: 'italic', padding: '16px' }}>No in-season data yet.</p>
  }

  // Build rows + zone dividers
  const tableItems = []
  let lastZoneId = null
  displayRows.forEach((r, idx) => {
    const zone = ZONE_MAP[r._zoneId]
    if (!isSorted && r._zoneId !== lastZoneId) {
      lastZoneId = r._zoneId
      tableItems.push({ _divider: true, zone, key: `div-${idx}` })
    }
    tableItems.push({ _divider: false, r, zone, key: `row-${r._pos}` })
  })

  const th = (colKey, label, align = 'left') => (
    <SortTH colKey={colKey} activeKey={sortKey} dir={sortDir} onSort={handleSort} align={align}>
      {label}
    </SortTH>
  )

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Playoff Picture</span>
        {isSorted && (
          <button onClick={reset} style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-faint)', background: 'none', border: '1px solid var(--border)', borderRadius: '4px', padding: '2px 8px', cursor: 'pointer' }}>
            Reset ×
          </button>
        )}
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '16px', minWidth: '480px' }}>
          <thead>
            <tr>
              {th('owner',        'Owner')}
              {th('actual_wins',  'W-L',     'right')}
              {th('pts_for',      'Pts',     'right')}
              {th('_back',        'Back',    'right')}
              {th('sim_wins',     'Sim',     'right')}
              {th('_winPctDiff',  'Diff',    'right')}
              {th('luck_diff',    'Verdict', 'right')}
              <th style={{ padding: '8px 10px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>
                {oppHeader}
              </th>
            </tr>
          </thead>
          <tbody>
            {tableItems.map(item => {
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
              const { r, zone } = item
              const pts = r.pts_for != null ? Number(r.pts_for).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—'
              const back    = formatDelta(r._back)
              const diff    = r._winPctDiff
              const diffAbs = Math.abs(diff * 100).toFixed(1)
              const diffStr = diff > 0 ? `+${diffAbs}%` : diff < 0 ? `-${diffAbs}%` : '0.0%'
              const diffColor = diff > 0 ? 'var(--green)' : diff < 0 ? 'var(--brand-red)' : 'var(--text-muted)'
              const wl    = wlStyle(r.actual_wins, r.actual_losses)
              const simWl = wlStyle(r.sim_wins, r.sim_losses)
              const verdict = luckVerdictFromDiff(r.luck_diff)
              return (
                <tr key={item.key} className="standings-row" style={{ borderBottom: '1px solid var(--border)', background: zone.bg }}>
                  <td style={{ padding: '8px 10px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                    {finishEmoji[r.owner] && <span style={{ marginRight: '5px' }}>{finishEmoji[r.owner]}</span>}
                    {r.owner}
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span style={{ ...wl, borderRadius: '4px', padding: '2px 5px', fontSize: '11px', fontWeight: 600 }}>{r.actual_wins}-{r.actual_losses}</span>
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{pts}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', color: back.color }}>{back.text}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span style={{ ...simWl, borderRadius: '4px', padding: '2px 5px', fontSize: '11px', fontWeight: 600 }}>{r.sim_wins}-{r.sim_losses}</span>
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, whiteSpace: 'nowrap', color: diffColor }}>{diffStr}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap', color: verdictColor(verdict), fontWeight: 500 }}>{verdict ?? '—'}</td>
                  <td style={{ padding: '8px 10px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
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

// ─── Race to the Bottom ───────────────────────────────────────────────────────

function RaceToBottom({ rows }) {
  const { sortKey, sortDir, handleSort } = useSort('asc')

  // Anchor: the team with the lowest optimal_pts (they're winning the race)
  const baseOpt = rows[0]?.optimal_pts ?? null

  const displayRows = useMemo(() => applySort(rows, sortKey, sortDir), [rows, sortKey, sortDir])

  if (!rows || rows.length === 0) return null

  const th = (colKey, label, align = 'left') => (
    <SortTH colKey={colKey} activeKey={sortKey} dir={sortDir} onSort={handleSort} align={align}>
      {label}
    </SortTH>
  )

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden', marginTop: '20px' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Race to the Bottom</span>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '16px' }}>
          <thead>
            <tr>
              {th('draft_pick',  '#')}
              {th('owner',       'Owner')}
              {th('actual_wins', 'W-L',      'right')}
              {th('optimal_pts', 'Opt PF',   'right')}
              {th('_ptsAhead',   'Pts Ahead','right')}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((r, i) => {
              const isLeader = r.draft_pick === 1
              const wl = wlStyle(r.actual_wins, r.actual_losses)
              const optPts = r.optimal_pts != null
                ? Number(r.optimal_pts).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
                : '—'
              const ahead = formatDelta(r._ptsAhead)
              return (
                <tr key={i} className="standings-row" style={{ borderBottom: '1px solid var(--border)', background: 'rgba(204,31,46,0.04)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 700, fontSize: '11px' }}>
                    {r.draft_pick != null ? (
                      <span style={{ background: isLeader ? 'rgba(204,31,46,0.2)' : 'rgba(204,31,46,0.1)', color: 'var(--brand-red)', borderRadius: '4px', padding: '2px 6px' }}>
                        #{r.draft_pick}
                      </span>
                    ) : '—'}
                  </td>
                  <td style={{ padding: '8px 10px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{r.owner}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span style={{ ...wl, borderRadius: '4px', padding: '2px 5px', fontSize: '11px', fontWeight: 600 }}>{r.actual_wins}-{r.actual_losses}</span>
                  </td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{optPts}</td>
                  <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', color: ahead.color }}>{ahead.text}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
        <p style={{ fontSize: '10px', color: 'var(--text-faint)', margin: 0 }}>
          Ranked by lowest optimal PF — weakest roster earns the 1st rookie draft pick
        </p>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function InSeason({ embedded = false }) {
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

  const { data: historyData } = useQuery({
    queryKey: ['history-season', activeSeason],
    queryFn: () => fetch(`/api/history/season/${activeSeason}`).then(r => r.json()),
    enabled: !!activeSeason,
  })

  // Map owner name → trophy emoji for completed seasons
  const finishEmoji = useMemo(() => {
    const map = {}
    for (const row of historyData?.standings ?? []) {
      if (row.finish === 'Champion')   map[row.owner] = '🏆'
      else if (row.finish === 'Runner-up') map[row.owner] = '🥈'
      else if (row.finish === '3rd')   map[row.owner] = '🥉'
    }
    return map
  }, [historyData])

  // Compute canonical zone order from snapshot rows:
  //   Playoff  (0–3): top 4 by W-L / pts_for (API sort)
  //   Wild Card (4–5): top 2 pts scorers from remaining 8
  //   Eliminated (6–11): remaining 6 by pts_for desc
  const zoneRows = useMemo(() => {
    const raw = snapshotData?.rows ?? []
    if (raw.length === 0) return []
    const top4 = raw.slice(0, 4)
    const rest = [...raw.slice(4)].sort((a, b) => (b.pts_for ?? 0) - (a.pts_for ?? 0))
    return [
      ...top4.map((r, i) => ({ ...r, _pos: i, _zoneId: 'playoff' })),
      ...rest.slice(0, 2).map((r, i) => ({ ...r, _pos: 4 + i, _zoneId: 'wildcard' })),
      ...rest.slice(2).map((r, i)    => ({ ...r, _pos: 6 + i, _zoneId: 'eliminated' })),
    ]
  }, [snapshotData])

  // Merge eliminated zone rows with RTB optimal_pts data, sorted by optimal_pts asc
  const rtbRows = useMemo(() => {
    const eliminated = zoneRows.filter(r => r._zoneId === 'eliminated')
    const rtbByOwner = Object.fromEntries((rtbData?.rows ?? []).map(r => [r.owner, r]))
    const merged = eliminated.map(r => ({
      ...r,
      optimal_pts: rtbByOwner[r.owner]?.optimal_pts ?? null,
      draft_pick:  rtbByOwner[r.owner]?.draft_pick  ?? null,
    })).sort((a, b) => (a.optimal_pts ?? Infinity) - (b.optimal_pts ?? Infinity))

    // Attach _ptsAhead: how many more opt pts vs the leader (null for leader)
    const base = merged[0]?.optimal_pts ?? null
    return merged.map((r, i) => ({
      ...r,
      _ptsAhead: i === 0 ? null : (r.optimal_pts != null && base != null ? r.optimal_pts - base : null),
    }))
  }, [zoneRows, rtbData])

  if (loadSeasons) return <LoadingSpinner />

  return (
    <div>
      {!embedded && (
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '28px', letterSpacing: '2px', marginBottom: '24px' }}>In-Season</h1>
      )}

      {/* Season selector — only shown when multiple seasons are available */}
      {seasons.length > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
          <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-faint)' }}>Season</span>
          <select
            value={activeSeason ?? ''}
            onChange={e => setSelectedSeason(Number(e.target.value))}
            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-mid)', borderRadius: '6px', padding: '5px 10px', fontSize: '13px', color: 'var(--text-primary)', fontFamily: 'var(--font-body)', outline: 'none' }}
          >
            {seasons.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      )}

      {(loadSnap || loadRTB) ? <LoadingSpinner /> : (
        <>
          <PlayoffPicture zoneRows={zoneRows} nextWeek={snapshotData?.next_week} finishEmoji={finishEmoji} />
          <RaceToBottom rows={rtbRows} />
        </>
      )}
    </div>
  )
}
