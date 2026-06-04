/**
 * DynastyRankings.jsx — Long-term dynasty power rankings panel.
 *
 * Ranks all 12 owners by dynasty strength using three components:
 *   Roster Score   (55%) — DynastyProcess value_2qb for all players; taxi at 80%
 *   Capital Score  (30%) — Future draft picks owned × DynastyProcess pick values
 *   Age Score      (15%) — Value-weighted avg age; younger rosters score higher
 *
 * All component scores are normalised 0–100 within the league.
 * Data sourced from DynastyProcess GitHub CSVs (refreshed weekly).
 *
 * Props:
 *   season  {number} — active season year
 */
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '../components/LoadingSpinner'

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

function scoreBar(value) {
  const color = value >= 70 ? 'var(--green)' : value >= 40 ? 'var(--gold)' : 'var(--brand-red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{ flex: 1, height: '4px', background: 'var(--border)', borderRadius: '2px', minWidth: '40px' }}>
        <div style={{ width: `${value}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width 0.3s' }} />
      </div>
      <span style={{ fontSize: '11px', fontVariantNumeric: 'tabular-nums', color, fontWeight: 600, minWidth: '28px', textAlign: 'right' }}>
        {value.toFixed(0)}
      </span>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function DynastyRankings({ season }) {
  const { data, isLoading } = useQuery({
    queryKey: ['dynasty-rankings', season],
    queryFn: () => fetch(`/api/in-season/dynasty-rankings/${season}`).then(r => r.json()),
    enabled: !!season,
  })

  if (isLoading) return <div style={{ padding: '20px 0' }}><LoadingSpinner /></div>

  const rows      = data?.rows ?? []
  const dataDate  = data?.data_date ?? null

  if (rows.length === 0) {
    return (
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Dynasty Rankings</span>
        </div>
        <p style={{ padding: '24px 16px', fontSize: '13px', color: 'var(--text-faint)', fontStyle: 'italic', textAlign: 'center' }}>
          Dynasty rankings available after the first weekly data refresh.
        </p>
      </div>
    )
  }

  const TH = ({ children, align = 'left', title, width }) => (
    <th title={title} style={{
      padding: '8px 10px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px',
      textTransform: 'uppercase', color: 'var(--text-faint)', background: 'var(--bg-page)',
      borderBottom: '1px solid var(--border)', textAlign: align, whiteSpace: 'nowrap',
      ...(width ? { width } : {}),
    }}>
      {children}
    </th>
  )

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Panel header */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Dynasty Rankings
        </span>
        {dataDate && (
          <span style={{ background: 'rgba(26,58,107,0.3)', color: '#5b8dd9', border: '1px solid rgba(91,141,217,0.2)', borderRadius: '4px', padding: '2px 7px', fontSize: '10px', fontWeight: 600 }}>
            {dataDate}
          </span>
        )}
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-faint)' }}>
          Roster 55% · Capital 30% · Age 15%
        </span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', minWidth: '560px' }}>
          <thead>
            <tr>
              <TH width="36px">#</TH>
              <TH>Owner</TH>
              <TH align="right" title="Composite dynasty score (0–100)">Score</TH>
              <TH title="Roster value from DynastyProcess SuperFlex values (0–100)" width="110px">Roster</TH>
              <TH title="Future draft pick capital value (0–100)" width="110px">Capital</TH>
              <TH title="Age curve: younger rosters score higher (0–100)" width="110px">Age</TH>
              <TH align="right">W-L</TH>
              <TH align="right">Pts For</TH>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const rs  = rankStyle(r.rank)
              const wl  = wlStyle(r.actual_wins, r.actual_losses)
              const pts = r.pts_for != null
                ? Number(r.pts_for).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
                : '—'

              return (
                <tr key={r.rank} className="standings-row" style={{ borderBottom: '1px solid var(--border)' }}>
                  {/* Rank */}
                  <td style={{ padding: '8px 10px' }}>
                    <div style={{ width: '22px', height: '22px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 700, background: rs.bg, color: rs.text }}>
                      {r.rank}
                    </div>
                  </td>

                  {/* Owner */}
                  <td style={{ padding: '8px 10px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                    {r.owner}
                  </td>

                  {/* Composite score */}
                  <td style={{ padding: '8px 10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: '18px', letterSpacing: '0.5px', color: 'var(--text-primary)', lineHeight: 1 }}>
                      {r.composite.toFixed(1)}
                    </span>
                  </td>

                  {/* Roster bar */}
                  <td style={{ padding: '6px 10px' }}>{scoreBar(r.roster_score)}</td>

                  {/* Capital bar */}
                  <td style={{ padding: '6px 10px' }}>{scoreBar(r.capital_score)}</td>

                  {/* Age bar */}
                  <td style={{ padding: '6px 10px' }}>{scoreBar(r.age_score)}</td>

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
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div style={{ padding: '8px 14px', borderTop: '1px solid var(--border)' }}>
        <p style={{ fontSize: '10px', color: 'var(--text-faint)', margin: 0 }}>
          Values via DynastyProcess (SuperFlex) · Taxi squad at 80% · Picks 3 years out
        </p>
      </div>
    </div>
  )
}
