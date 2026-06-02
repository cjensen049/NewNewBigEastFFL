import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '../components/LoadingSpinner'

// ─── Shared helpers ───────────────────────────────────────────────────────────

const CONTAINER = { maxWidth: '1280px', margin: '0 auto', padding: '0 24px' }

function SectionLabel({ children }) {
  return (
    <p style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '12px' }}>
      {children}
    </p>
  )
}

// ─── Hero section ─────────────────────────────────────────────────────────────

function Hero() {
  return (
    <div style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)', position: 'relative', overflow: 'hidden' }}>
      {/* Radial glow top-right */}
      <div style={{
        position: 'absolute', top: 0, right: 0, width: '500px', height: '250px',
        background: 'radial-gradient(ellipse, rgba(204,31,46,0.1) 0%, transparent 65%)',
        pointerEvents: 'none',
      }} />

      <div style={{ ...CONTAINER, padding: '28px 24px 24px', position: 'relative' }}>
        {/* Established badge */}
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'rgba(26,58,107,0.3)', border: '1px solid var(--border-mid)', borderRadius: '20px', padding: '4px 14px', marginBottom: '14px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--brand-red)', flexShrink: 0 }} />
          <span style={{ fontSize: '11px', fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Established</span>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--brand-red)' }}>2021</span>
        </div>

        {/* Two-line title */}
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '44px', letterSpacing: '3px', lineHeight: 1, margin: 0 }}>
          <div>
            <span style={{ fontStyle: 'italic', color: 'var(--text-muted)' }}>The NEW </span>
            <span style={{ color: 'var(--text-primary)' }}>NEW BIG EAST</span>
          </div>
          <div style={{ color: 'var(--brand-red)' }}>FANTASY FOOTBALL</div>
        </h1>
      </div>
    </div>
  )
}

// ─── Explore cards ────────────────────────────────────────────────────────────

const NAV_CARDS = [
  {
    to: '/league',
    icon: '🏆',
    title: 'League History',
    description: 'All-time standings, records, head-to-head matchups, schedule luck, and full draft history.',
    accentStyle: { background: 'var(--brand-navy)' },
    iconBg: 'rgba(26,58,107,0.3)',
  },
  {
    to: '/owner',
    icon: '👤',
    title: 'Owner Dashboard',
    description: 'Individual profiles — career summary, draft picks, trade activity, waiver trends, and rivalry matchups.',
    accentStyle: { background: 'var(--brand-red)' },
    iconBg: 'rgba(204,31,46,0.15)',
  },
  {
    to: '/transactions',
    icon: '🔄',
    title: 'Transaction History',
    description: 'Trade timelines, waiver wire activity, and transaction patterns across all seasons.',
    accentStyle: { background: 'linear-gradient(to right, var(--brand-navy), var(--brand-red))' },
    iconBg: 'rgba(26,58,107,0.25)',
  },
]

function ExploreSection() {
  return (
    <div style={{ padding: '28px 0 24px' }}>
      <SectionLabel>Explore</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
        {NAV_CARDS.map(card => (
          <Link key={card.to} to={card.to} className="explore-card">
            {/* Top accent bar */}
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '3px', borderRadius: '10px 10px 0 0', ...card.accentStyle }} />

            {/* Icon box */}
            <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: card.iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px', marginBottom: '12px' }}>
              {card.icon}
            </div>

            <p style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>{card.title}</p>
            <p style={{ fontSize: '11.5px', color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '16px' }}>{card.description}</p>

            <span className="card-arrow">↗</span>
          </Link>
        ))}
      </div>
    </div>
  )
}

// ─── Standings panel ──────────────────────────────────────────────────────────

function wlStyle(wins, losses) {
  if (wins > losses) return { background: 'rgba(63,185,80,0.12)', color: 'var(--green)' }
  if (losses > wins) return { background: 'rgba(204,31,46,0.1)', color: 'var(--brand-red)' }
  return { background: 'rgba(227,179,65,0.12)', color: 'var(--gold)' }
}

function rankStyle(i) {
  if (i === 0) return { background: 'rgba(204,31,46,0.2)', color: 'var(--brand-red)' }
  if (i === 1) return { background: 'rgba(26,58,107,0.3)', color: '#5b8dd9' }
  return { background: 'var(--border)', color: 'var(--text-muted)' }
}

function StandingsPanel() {
  const { data: seasonsData, isLoading: loadSeasons } = useQuery({
    queryKey: ['inseason-seasons'],
    queryFn: () => fetch('/api/in-season/seasons').then(r => r.json()),
  })

  const seasons = seasonsData?.seasons ?? []
  const currentSeason = seasons[0]

  const { data, isLoading } = useQuery({
    queryKey: ['inseason-snapshot', currentSeason],
    queryFn: () => fetch(`/api/in-season/snapshot/${currentSeason}`).then(r => r.json()),
    enabled: !!currentSeason,
  })

  if (loadSeasons || isLoading) return <LoadingSpinner />

  const rows = data?.rows ?? []

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Panel header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Current Standings</span>
        {currentSeason && (
          <span style={{ background: 'rgba(26,58,107,0.3)', color: '#5b8dd9', border: '1px solid rgba(91,141,217,0.2)', borderRadius: '4px', padding: '2px 7px', fontSize: '10px', fontWeight: 600 }}>
            {currentSeason}
          </span>
        )}
        <Link to="/league" style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-faint)', textDecoration: 'none' }}>
          Full standings →
        </Link>
      </div>

      {rows.length === 0 ? (
        <p style={{ padding: '16px', fontSize: '13px', color: 'var(--text-faint)', fontStyle: 'italic' }}>No in-season data yet.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-page)' }}>
              <th style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', textAlign: 'left', width: '32px' }}>#</th>
              <th style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', textAlign: 'left' }}>Owner</th>
              <th style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', textAlign: 'right' }}>W-L</th>
              <th style={{ padding: '8px 12px', fontSize: '10px', fontWeight: 600, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-faint)', textAlign: 'right' }}>Pts</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const wl = wlStyle(r.actual_wins, r.actual_losses)
              const rk = rankStyle(i)
              const pts = r.pts_for != null ? Number(r.pts_for).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—'
              return (
                <tr key={i} className="standings-row" style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '9px 12px' }}>
                    <div style={{ width: '20px', height: '20px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 700, ...rk }}>
                      {i + 1}
                    </div>
                  </td>
                  <td style={{ padding: '9px 12px', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{r.owner}</td>
                  <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                    <span style={{ ...wl, borderRadius: '4px', padding: '2px 7px', fontSize: '12px', fontWeight: 600 }}>
                      {r.actual_wins}-{r.actual_losses}
                    </span>
                  </td>
                  <td style={{ padding: '9px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{pts}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

// ─── Calendar panel ───────────────────────────────────────────────────────────

const TYPE_ICON = { draft: '📋', dues: '💰', roster_deadline: '📝', regular_season: '🏈', trade_deadline: '⏰', playoffs: '⚔️', championship: '🏆' }

function CalendarPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ['calendar-events'],
    queryFn: () => fetch('/api/calendar/events').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />

  const events = data?.events ?? []
  if (events.length === 0) return null

  const currentSeason = events[0].season
  const currentEvents = events.filter(e => e.season === currentSeason)

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Panel header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Season Calendar</span>
        <span style={{ background: 'rgba(35,134,54,0.15)', color: 'var(--green)', border: '1px solid rgba(63,185,80,0.25)', borderRadius: '4px', padding: '2px 7px', fontSize: '10px', fontWeight: 600 }}>
          {currentSeason}
        </span>
        <Link to="/calendar" style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-faint)', textDecoration: 'none' }}>
          Full calendar →
        </Link>
      </div>

      <div>
        {currentEvents.map((e, i) => {
          const isActive = e.status === 'active' || e.status === 'drafting'
          const dateStr = e.date_start_fmt
            ? e.date_end_fmt && e.date_end_fmt !== e.date_start_fmt
              ? `${e.date_start_fmt} – ${e.date_end_fmt}`
              : e.date_start_fmt
            : null

          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '9px 16px',
              borderBottom: i < currentEvents.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              {/* Status dot */}
              <div style={{
                width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0,
                background: isActive ? 'var(--brand-red)' : 'var(--border)',
                ...(isActive ? { boxShadow: '0 0 6px rgba(204,31,46,0.5)' } : {}),
              }} />

              {/* Icon + name */}
              <span style={{ fontSize: '14px', flexShrink: 0 }}>{TYPE_ICON[e.type] ?? '📅'}</span>
              <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-primary)', flex: 1, minWidth: 0 }}>{e.title}</span>

              {/* Date */}
              {dateStr && <span style={{ fontSize: '11px', color: 'var(--text-faint)', flexShrink: 0 }}>{dateStr}</span>}

              {/* Status label */}
              {isActive ? (
                <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--brand-red)', background: 'rgba(204,31,46,0.12)', borderRadius: '4px', padding: '2px 8px', flexShrink: 0 }}>Active</span>
              ) : (
                <span style={{ fontSize: '10px', color: 'var(--text-faint)', flexShrink: 0 }}>
                  {e.status === 'complete' ? 'Complete' : 'Upcoming'}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── This Season section ──────────────────────────────────────────────────────

function ThisSeasonSection() {
  return (
    <div style={{ paddingBottom: '32px' }}>
      <SectionLabel>This Season</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <StandingsPanel />
        <CalendarPanel />
      </div>
    </div>
  )
}

// ─── Page root ────────────────────────────────────────────────────────────────

export default function Home() {
  return (
    <div>
      <Hero />
      <div style={CONTAINER}>
        <ExploreSection />
        <ThisSeasonSection />
      </div>
    </div>
  )
}
