import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '../components/LoadingSpinner'
import DataTable from '../components/DataTable'

// ─── Shared helpers ───────────────────────────────────────────────────────────

const CONTAINER = { maxWidth: '1280px', margin: '0 auto', padding: '0 clamp(12px, 3vw, 24px)' }

function SectionLabel({ children }) {
  return (
    <p className="fs-label" style={{ fontWeight: 600, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '12px' }}>
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

      <div style={{ ...CONTAINER, padding: 'clamp(20px, 4vw, 28px) clamp(12px, 3vw, 24px) 24px', position: 'relative' }}>
        {/* Established badge */}
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'rgba(26,58,107,0.3)', border: '1px solid var(--border-mid)', borderRadius: '20px', padding: '4px 14px', marginBottom: '14px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--brand-red)', flexShrink: 0 }} />
          <span className="fs-label" style={{ fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Established</span>
          <span className="fs-label" style={{ fontWeight: 700, color: 'var(--brand-red)' }}>2021</span>
        </div>

        {/* Logo + two-line title */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '20px' }}>
          <img
            src="/logo.png"
            alt="NNBE"
            className="hero-logo"
            onError={e => { e.target.style.display = 'none' }}
          />
          <h1 className="hero-title" style={{ fontFamily: 'var(--font-display)', margin: 0 }}>
            <div>
              <span style={{ fontStyle: 'italic', color: 'var(--text-muted)' }}>The NEW </span>
              <span style={{ color: 'var(--text-primary)' }}>NEW BIG EAST</span>
            </div>
            <div style={{ color: 'var(--brand-red)' }}>FANTASY FOOTBALL</div>
          </h1>
        </div>
      </div>
    </div>
  )
}

// ─── Quick links ──────────────────────────────────────────────────────────────

const QUICK_LINKS = [
  {
    to: '/league?tab=rankings',
    icon: '📈',
    title: 'Power Rankings',
    description: 'Weekly standings by scoring, record, and schedule strength — plus long-term dynasty rankings.',
    accentStyle: { background: 'var(--brand-navy)' },
    iconBg: 'rgba(26,58,107,0.3)',
  },
  {
    to: '/league?tab=inseason',
    icon: '🏆',
    title: 'Playoff Picture',
    description: 'Live playoff odds, clinching scenarios, race to the bottom, and schedule luck scores.',
    accentStyle: { background: 'var(--brand-red)' },
    iconBg: 'rgba(204,31,46,0.15)',
  },
  {
    to: '/owner',
    icon: '👥',
    title: 'Owners Dashboard',
    description: 'Career stats, championships, head-to-head records, and roster history for every owner.',
    accentStyle: { background: 'var(--gold)' },
    iconBg: 'rgba(227,179,65,0.15)',
  },
  {
    to: '/transactions',
    icon: '🔄',
    title: 'Trade Tree',
    description: 'Trace any player or pick’s full trade history — every hop, forward and back, across seasons.',
    accentStyle: { background: 'linear-gradient(to right, var(--brand-navy), var(--brand-red))' },
    iconBg: 'rgba(26,58,107,0.25)',
  },
]

function ExploreSection() {
  return (
    <div style={{ padding: '28px 0 24px' }}>
      <SectionLabel>Quick Links</SectionLabel>
      <div className="home-explore-grid">
        {QUICK_LINKS.map(card => (
          <Link key={card.to} to={card.to} className="explore-card">
            {/* Top accent bar */}
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '3px', borderRadius: '10px 10px 0 0', ...card.accentStyle }} />

            {/* Icon box */}
            <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: card.iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px', marginBottom: '12px' }}>
              {card.icon}
            </div>

            <p className="fs-card-title" style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>{card.title}</p>
            <p className="fs-body" style={{ color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: '16px' }}>{card.description}</p>

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

function luckVerdict(luckDiff) {
  if (luckDiff == null) return null
  if (luckDiff > 0.3) return { label: '↑ Lucky',   color: 'var(--green)',     bg: 'rgba(63,185,80,0.1)' }
  if (luckDiff < -0.3) return { label: '↓ Unlucky', color: 'var(--brand-red)', bg: 'rgba(204,31,46,0.08)' }
  return { label: '→ Even',   color: 'var(--gold)',      bg: 'rgba(227,179,65,0.1)' }
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
  const nextWeek = data?.next_week
  const oppHeader = nextWeek ? `Wk ${nextWeek} Opp` : 'Next Opp'

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Panel header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span className="fs-title" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Current Standings</span>
        {currentSeason && (
          <span className="fs-label" style={{ background: 'rgba(26,58,107,0.3)', color: '#5b8dd9', border: '1px solid rgba(91,141,217,0.2)', borderRadius: '4px', padding: '2px 7px', fontWeight: 600 }}>
            {currentSeason}
          </span>
        )}
        <Link to="/league?tab=inseason" className="fs-label" style={{ marginLeft: 'auto', color: 'var(--text-faint)', textDecoration: 'none' }}>
          Full standings →
        </Link>
      </div>

      {rows.length === 0 ? (
        <p className="fs-body" style={{ padding: '16px', color: 'var(--text-faint)', fontStyle: 'italic' }}>No in-season data yet.</p>
      ) : (
        <DataTable
          rows={rows}
          maxHeight="460px"
          minWidth="340px"
          bordered={false}
          columns={[
            {
              key: '_rank', label: '#', sortable: false,
              render: (_, __, i) => (
                <div style={{ width: '20px', height: '20px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 700, ...rankStyle(i) }}>
                  {i + 1}
                </div>
              ),
            },
            { key: 'owner', label: 'Owner' },
            {
              key: 'actual_wins', label: 'W-L', align: 'right',
              render: (_, r) => (
                <span style={{ ...wlStyle(r.actual_wins, r.actual_losses), borderRadius: '4px', padding: '2px 6px', fontSize: '11px', fontWeight: 600, whiteSpace: 'nowrap' }}>
                  {r.actual_wins}-{r.actual_losses}
                </span>
              ),
            },
            {
              key: 'pts_for', label: 'Pts For', align: 'right',
              render: v => v != null ? Number(v).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—',
            },
            {
              key: 'luck_diff', label: 'Luck', align: 'center',
              render: v => {
                const verdict = luckVerdict(v)
                return verdict ? (
                  <span style={{ background: verdict.bg, color: verdict.color, borderRadius: '4px', padding: '2px 6px', fontSize: '11px', fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {verdict.label}
                  </span>
                ) : null
              },
            },
            {
              key: 'next_opponent', label: oppHeader,
              render: v => v ?? <span style={{ color: 'var(--text-faint)', fontStyle: 'italic' }}>—</span>,
            },
          ]}
        />
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
        <span className="fs-title" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Season Calendar</span>
        <span className="fs-label" style={{ background: 'rgba(35,134,54,0.15)', color: 'var(--green)', border: '1px solid rgba(63,185,80,0.25)', borderRadius: '4px', padding: '2px 7px', fontWeight: 600 }}>
          {currentSeason}
        </span>
        <Link to="/calendar" className="fs-label" style={{ marginLeft: 'auto', color: 'var(--text-faint)', textDecoration: 'none' }}>
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
              <span className="fs-body" style={{ fontWeight: 500, color: 'var(--text-primary)', flex: 1, minWidth: 0 }}>{e.title}</span>

              {/* Date */}
              {dateStr && <span className="fs-label" style={{ color: 'var(--text-faint)', flexShrink: 0 }}>{dateStr}</span>}

              {/* Status label */}
              {isActive ? (
                <span className="fs-label" style={{ fontWeight: 600, color: 'var(--brand-red)', background: 'rgba(204,31,46,0.12)', borderRadius: '4px', padding: '2px 8px', flexShrink: 0 }}>Active</span>
              ) : (
                <span className="fs-label" style={{ color: 'var(--text-faint)', flexShrink: 0 }}>
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

// ─── League resources section ─────────────────────────────────────────────────

const RESOURCE_LINKS = [
  {
    href: 'https://docs.google.com/document/d/1dJn0QMIQJVdLu63IDUQ147Mut7E-DMKHHFuc3XnvxQc/edit?tab=t.0',
    icon: '📄',
    title: 'League Bylaws',
    desc: 'Rules, scoring settings, roster requirements, and commissioner policies.',
  },
  {
    href: 'https://docs.google.com/spreadsheets/d/1Tk0I7NaAw-Vp-5dyg8NR3viDcY7qKA72u_kFYRaOBVU/edit?gid=0#gid=0',
    icon: '💰',
    title: 'Finances & Dues',
    desc: 'League dues, payouts, and historical financial records.',
  },
]

function ResourcesSection() {
  return (
    <div style={{ paddingBottom: '28px' }}>
      <SectionLabel>League Resources</SectionLabel>
      <div className="home-resources-grid">
        {RESOURCE_LINKS.map(link => (
          <a
            key={link.href}
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="resource-link-card"
          >
            <span style={{ position: 'absolute', top: '12px', right: '14px', fontSize: '13px', color: 'var(--text-faint)' }}>↗</span>
            <div style={{ fontSize: '20px', marginBottom: '8px' }}>{link.icon}</div>
            <p className="fs-title" style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>{link.title}</p>
            <p className="fs-body" style={{ color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>{link.desc}</p>
          </a>
        ))}
      </div>
    </div>
  )
}

// ─── This Season section ──────────────────────────────────────────────────────

function ThisSeasonSection() {
  return (
    <div style={{ paddingBottom: '32px' }}>
      <SectionLabel>This Season</SectionLabel>
      <div className="home-season-grid">
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
        <ResourcesSection />
      </div>
    </div>
  )
}
