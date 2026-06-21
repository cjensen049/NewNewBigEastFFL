/**
 * Sidebar.jsx — persistent site navigation.
 *
 * Desktop (md+): fixed 220px left sidebar. Logo area at top, nav items in
 *   the middle, "2021 – present" label pinned to the bottom.
 *   League sub-sections expand inline when on any /league route.
 *
 * Mobile (<md): sticky 52px top bar with hamburger icon. Tapping the hamburger
 *   slides the full sidebar in from the left as an overlay; tapping the overlay
 *   or any nav item closes it.
 */
import { useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'

const TOP_NAV = [
  { to: '/',             label: 'Home',         emoji: '🏠', end: true },
  { to: '/league',       label: 'League',       emoji: '🏆' },
  { to: '/owner',        label: 'Owners',       emoji: '👤' },
  { to: '/transactions', label: 'Transactions', emoji: '🔄' },
]

const LEAGUE_SUBS = [
  { tab: 'inseason',  label: 'In-Season',      emoji: '📅' },
  { tab: 'rankings',  label: 'Power Rankings', emoji: '🏆' },
  { tab: 'history',   label: 'History',        emoji: '📊' },
  { tab: 'h2h',       label: 'Head-to-Head',   emoji: '⚔️' },
  { tab: 'draft',     label: 'Draft',          emoji: '📋' },
  { tab: 'schedule',  label: 'Schedule',       emoji: '🗓' },
]

function Wordmark() {
  return (
    <span style={{ fontFamily: 'var(--font-display)', fontSize: '26px', letterSpacing: '2px', lineHeight: 1 }}>
      <span style={{ color: '#f0f0f0' }}>N</span>
      <span style={{ color: '#f0f0f0' }}>N</span>
      <span style={{ color: '#cc1f2e' }}>B</span>
      <span style={{ color: '#4a7fd4' }}>E</span>
    </span>
  )
}

function SidebarContent({ onNavClick }) {
  const location = useLocation()
  const isLeague = location.pathname.startsWith('/league')
  const activeTab = new URLSearchParams(location.search).get('tab') || 'inseason'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Logo area */}
      <div style={{ padding: '20px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <Link to="/" onClick={onNavClick} style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
          <img
            src="/logo.png"
            alt="NNBE"
            style={{ height: '60px', width: '60px', borderRadius: '10px', objectFit: 'contain', filter: 'drop-shadow(0 0 8px rgba(204,31,46,0.3))' }}
            onError={e => { e.target.style.display = 'none' }}
          />
          <Wordmark />
        </Link>
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, paddingTop: '8px', overflowY: 'auto' }}>
        {TOP_NAV.map(item => (
          <div key={item.to}>
            <NavLink
              to={item.to}
              end={item.end}
              onClick={onNavClick}
              className={({ isActive }) => `sidebar-nav-item${isActive ? ' active' : ''}`}
            >
              <span>{item.emoji}</span>
              <span>{item.label}</span>
            </NavLink>

            {/* League sub-items — visible only when on any /league route */}
            {item.to === '/league' && isLeague && (
              <div>
                {LEAGUE_SUBS.map(sub => (
                  <Link
                    key={sub.tab}
                    to={`/league?tab=${sub.tab}`}
                    onClick={onNavClick}
                    className={`sidebar-sub-item${activeTab === sub.tab ? ' active' : ''}`}
                  >
                    <span>{sub.emoji}</span>
                    <span>{sub.label}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
        <p style={{ fontSize: '11px', color: 'var(--text-faint)', margin: 0 }}>2021 – present</p>
      </div>

    </div>
  )
}

export default function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const close = () => setMobileOpen(false)

  return (
    <>
      {/* ── Desktop sidebar — always visible at md+ ─────────────────── */}
      <div className="hidden md:block" style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '220px',
        height: '100vh',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        zIndex: 100,
      }}>
        <SidebarContent onNavClick={() => {}} />
      </div>

      {/* ── Mobile top bar — visible below md ───────────────────────── */}
      <div className="md:hidden" style={{
        position: 'sticky',
        top: 0,
        zIndex: 99,
        height: '52px',
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
      }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
          <img
            src="/logo.png"
            alt="NNBE"
            style={{ height: '44px', width: '44px', borderRadius: '8px', objectFit: 'contain', filter: 'drop-shadow(0 0 6px rgba(204,31,46,0.25))' }}
            onError={e => { e.target.style.display = 'none' }}
          />
          <Wordmark />
        </Link>
        <button
          onClick={() => setMobileOpen(true)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '10px 8px', display: 'flex', alignItems: 'center' }}
          aria-label="Open navigation"
        >
          <svg width="20" height="16" viewBox="0 0 20 16" fill="none">
            <path d="M0 1h20M0 8h20M0 15h20" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* ── Mobile overlay — closes sidebar on tap ───────────────────── */}
      {mobileOpen && (
        <div
          onClick={close}
          className="md:hidden"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 199 }}
        />
      )}

      {/* ── Mobile slide-in sidebar ──────────────────────────────────── */}
      <div
        className="md:hidden"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '280px',
          height: '100vh',
          background: 'var(--bg-surface)',
          zIndex: 200,
          transform: mobileOpen ? 'translateX(0)' : 'translateX(-100%)',
          transition: 'transform 0.25s ease',
        }}
      >
        <SidebarContent onNavClick={close} />
      </div>
    </>
  )
}
