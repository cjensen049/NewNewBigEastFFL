/**
 * OwnerRoster.jsx — Owner landing page.
 *
 * Displays a card grid of all league owners. Each card shows the owner's
 * Sleeper avatar, name, membership info, and career accolades. Clicking a
 * card navigates to /owner/:name for the full profile.
 *
 * Sort order: active owners first (champions → win%), departed owners last.
 */
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import LoadingSpinner from '../components/LoadingSpinner'

const CONTAINER = { maxWidth: '1280px', margin: '0 auto', padding: 'clamp(12px, 3vw, 24px)' }

function initials(name) {
  if (!name) return '??'
  return name.split(' ').map(w => w[0] ?? '').join('').slice(0, 2).toUpperCase()
}

function wlColor(record) {
  if (!record || record === '—') return 'var(--text-muted)'
  const [w, l] = record.split('-').map(Number)
  if (w > l) return 'var(--green)'
  if (l > w) return 'var(--brand-red)'
  return 'var(--gold)'
}

function winPctColor(v) {
  const p = v * 100
  if (p < 40) return 'var(--brand-red)'
  if (p < 55) return 'var(--gold)'
  return 'var(--green)'
}

function MiniStat({ label, value, valueColor }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
      <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-faint)' }}>
        {label}
      </span>
      <span style={{ fontFamily: 'var(--font-display)', fontSize: '22px', lineHeight: 1, color: valueColor ?? 'var(--text-primary)' }}>
        {value ?? '—'}
      </span>
    </div>
  )
}

function OwnerCard({ owner }) {
  const navigate = useNavigate()
  const hasTitle = owner.championships > 0
  const isDeparted = !!owner.departed_after

  return (
    <div
      className="owner-roster-card"
      onClick={() => navigate(`/owner/${encodeURIComponent(owner.name)}`)}
      style={{ opacity: isDeparted ? 0.75 : 1 }}
    >
      {/* Championship banner */}
      {hasTitle && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          marginBottom: '14px',
          padding: '5px 10px',
          background: 'rgba(227,179,65,0.1)',
          border: '1px solid rgba(227,179,65,0.25)',
          borderRadius: '6px',
        }}>
          <span style={{ fontSize: '13px' }}>🏆</span>
          <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--gold)' }}>
            {owner.championships === 1 ? 'League Champion' : `${owner.championships}× Champion`}
          </span>
        </div>
      )}

      {/* Avatar + name row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '16px' }}>
        {owner.avatar_url ? (
          <img
            src={owner.avatar_url}
            alt={owner.name}
            style={{ width: '64px', height: '64px', borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--border-mid)', flexShrink: 0 }}
          />
        ) : (
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%', flexShrink: 0,
            border: '2px solid var(--border-mid)',
            background: 'linear-gradient(135deg, var(--brand-navy), var(--brand-red))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: '24px', color: '#fff', lineHeight: 1 }}>
              {initials(owner.name)}
            </span>
          </div>
        )}

        <div style={{ minWidth: 0 }}>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '28px', letterSpacing: '2px', lineHeight: 1, color: 'var(--text-primary)', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {owner.name}
          </p>
          <p style={{ fontSize: '12px', color: 'var(--text-faint)', marginTop: '5px', lineHeight: 1 }}>
            {owner.joined_season
              ? (owner.departed_after
                  ? `${owner.joined_season} – ${owner.departed_after}`
                  : `Since ${owner.joined_season}`)
              : (owner.total_seasons > 0 ? 'Since 2021' : 'Joining 2026')}
          </p>
          {isDeparted && (
            <span style={{ display: 'inline-block', marginTop: '4px', background: 'rgba(204,31,46,0.12)', color: 'var(--brand-red)', border: '1px solid rgba(204,31,46,0.25)', borderRadius: '4px', padding: '1px 7px', fontSize: '10px', fontWeight: 600 }}>
              Departed
            </span>
          )}
        </div>
      </div>

      {/* Stat grid row 1: Titles | Playoffs | Seasons */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px', paddingBottom: '12px', borderBottom: '1px solid var(--border)' }}>
        <MiniStat
          label="Titles"
          value={owner.championships}
          valueColor={owner.championships > 0 ? 'var(--gold)' : 'var(--text-muted)'}
        />
        <MiniStat
          label="Playoffs"
          value={owner.playoff_appearances}
          valueColor={owner.playoff_appearances > 0 ? 'var(--text-primary)' : 'var(--text-muted)'}
        />
        <MiniStat
          label="Seasons"
          value={owner.total_seasons || '—'}
          valueColor="var(--text-muted)"
        />
      </div>

      {/* Stat grid row 2: Record | Win% | Best Finish */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        <MiniStat
          label="Record"
          value={owner.record}
          valueColor={wlColor(owner.record)}
        />
        <MiniStat
          label="Win %"
          value={owner.total_seasons > 0 ? `${(owner.win_pct * 100).toFixed(0)}%` : '—'}
          valueColor={owner.total_seasons > 0 ? winPctColor(owner.win_pct) : 'var(--text-muted)'}
        />
        <MiniStat
          label="Best"
          value={owner.best_finish}
          valueColor={owner.best_finish === 'Champion' ? 'var(--gold)' : owner.best_finish === 'Runner-up' ? '#5b8dd9' : 'var(--text-muted)'}
        />
      </div>
    </div>
  )
}

export default function OwnerRoster() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['owners-summary'],
    queryFn: () => fetch('/api/owners/summary').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />
  if (error) return <div style={{ padding: '40px', color: 'var(--brand-red)' }}>Failed to load owners.</div>

  const owners = data?.owners ?? []

  return (
    <div style={CONTAINER}>
      {/* Page header */}
      <div style={{ marginBottom: '28px', paddingTop: '8px' }}>
        <p style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '2px', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '4px' }}>
          NNBE FOOTBALL
        </p>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '44px', letterSpacing: '3px', color: 'var(--text-primary)', margin: 0, lineHeight: 1 }}>
          OWNERS
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '8px' }}>
          {owners.filter(o => !o.departed_after).length} active members · since 2021
        </p>
      </div>

      <div className="owner-roster-grid">
        {owners.map(owner => (
          <OwnerCard key={owner.name} owner={owner} />
        ))}
      </div>
    </div>
  )
}
