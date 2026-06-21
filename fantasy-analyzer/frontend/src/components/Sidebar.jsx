/**
 * Sidebar.jsx — persistent site navigation.
 *
 * Desktop (md+): fixed 220px left sidebar. Logo area at top, nav items in
 *   the middle, "2021 – present" label pinned to the bottom.
 *   League sub-sections expand inline when on any /league route.
 *
 * Mobile (<md): sticky 52px top bar with hamburger icon. Tapping the hamburger
 *   slides the full sidebar in from the left as an overlay; tapping the overlay
 *   or any nav item closes it. Tapping a top-level item that has sub-sections
 *   (League, Transactions, Owners) expands them in place instead of navigating
 *   straight to the default tab — and a sub-section can itself expand further
 *   (e.g. League > Power Rankings > Weekly/Dynasty).
 */
import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'

const LEAGUE_SUBS = [
  { tab: 'inseason',  label: 'In-Season',      emoji: '📅' },
  {
    tab: 'rankings', label: 'Power Rankings', emoji: '🏆',
    views: [
      { view: 'weekly',  label: 'Weekly' },
      { view: 'dynasty', label: 'Dynasty' },
    ],
  },
  { tab: 'history',   label: 'History',        emoji: '📊' },
  { tab: 'h2h',       label: 'Head-to-Head',   emoji: '⚔️' },
  { tab: 'draft',     label: 'Draft',          emoji: '📋' },
  { tab: 'schedule',  label: 'Schedule',       emoji: '🗓' },
]

const TRANSACTIONS_SUBS = [
  { tab: 'tree',       label: 'Trade Tree',  emoji: '🌳' },
  { tab: 'log',        label: 'Trade Log',   emoji: '📜' },
  { tab: 'waivers',    label: 'Waivers',     emoji: '💰' },
  { tab: 'tendencies', label: 'Tendencies',  emoji: '📈' },
]

const OWNER_SUBS = [
  { tab: 'summary', label: 'Career Summary', emoji: '📋' },
  { tab: 'h2h',     label: 'Head-to-Head',   emoji: '⚔️' },
  { tab: 'players', label: 'Top Players',    emoji: '⭐' },
  { tab: 'draft',   label: 'Draft Picks',    emoji: '🏈' },
  { tab: 'trades',  label: 'Trades',         emoji: '🔄' },
  { tab: 'waivers', label: 'Waivers',        emoji: '💰' },
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

// ─── Mobile: a top-level item that expands into its sub-sections ─────────────
// Auto-expands when you're already in that section; can also be toggled by tap.

function ExpandableNavItem({ emoji, label, isActive, subItems, onNavClick, depth = 0 }) {
  const [open, setOpen] = useState(false)
  const showOpen = open || isActive

  // Auto-collapse once you've navigated away from this section, so leaving
  // it manually expanded doesn't leak into other pages.
  useEffect(() => {
    if (!isActive) setOpen(false)
  }, [isActive])

  const className = depth === 0 ? 'sidebar-nav-item' : 'sidebar-sub-item'

  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className={`${className}${isActive ? ' active' : ''}`}
        style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', justifyContent: 'space-between' }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 'inherit' }}>
          <span>{emoji}</span>
          <span>{label}</span>
        </span>
        <span style={{ fontSize: '10px', color: 'var(--text-faint)', transform: showOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>▶</span>
      </button>
      {showOpen && (
        <div>
          {subItems.map((sub, i) => (
            <SidebarLeafOrBranch key={i} {...sub} onNavClick={onNavClick} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

function SidebarLeafOrBranch({ emoji, label, href, isActive, subItems, onNavClick, depth }) {
  if (subItems) {
    return <ExpandableNavItem emoji={emoji} label={label} isActive={isActive} subItems={subItems} onNavClick={onNavClick} depth={depth} />
  }
  const className = depth <= 1 ? 'sidebar-sub-item' : 'sidebar-sub-sub-item'
  return (
    <Link to={href} onClick={onNavClick} className={`${className}${isActive ? ' active' : ''}`}>
      {emoji && <span>{emoji}</span>}
      <span>{label}</span>
    </Link>
  )
}

function SidebarContent({ onNavClick, isMobile }) {
  const location = useLocation()
  const searchParams = new URLSearchParams(location.search)

  const isLeague = location.pathname.startsWith('/league')
  const activeLeagueTab = searchParams.get('tab') || 'inseason'
  const activeView = searchParams.get('view') || 'weekly'

  const isTransactions = location.pathname.startsWith('/transactions')
  const activeTxnTab = searchParams.get('tab') || 'tree'

  const ownerMatch = location.pathname.match(/^\/owner\/([^/?]+)/)
  const currentOwnerName = ownerMatch ? decodeURIComponent(ownerMatch[1]) : null
  const activeOwnerTab = searchParams.get('tab') || 'summary'

  // Desktop keeps its original simple behavior: League subs auto-show when
  // on /league, no toggle buttons. Mobile gets the full expandable tree.
  const showLeagueSubsDesktop = isLeague

  const leagueSubItems = LEAGUE_SUBS.map(sub => sub.views
    ? {
        emoji: sub.emoji, label: sub.label,
        isActive: isLeague && activeLeagueTab === sub.tab,
        subItems: sub.views.map(v => ({
          label: v.label,
          href: `/league?tab=${sub.tab}&view=${v.view}`,
          isActive: isLeague && activeLeagueTab === sub.tab && activeView === v.view,
        })),
      }
    : {
        emoji: sub.emoji, label: sub.label,
        href: `/league?tab=${sub.tab}`,
        isActive: isLeague && activeLeagueTab === sub.tab,
      }
  )

  const txnSubItems = TRANSACTIONS_SUBS.map(sub => ({
    emoji: sub.emoji, label: sub.label,
    href: `/transactions?tab=${sub.tab}`,
    isActive: isTransactions && activeTxnTab === sub.tab,
  }))

  const ownerSubItems = currentOwnerName
    ? OWNER_SUBS.map(sub => ({
        emoji: sub.emoji, label: sub.label,
        href: `/owner/${encodeURIComponent(currentOwnerName)}?tab=${sub.tab}`,
        isActive: activeOwnerTab === sub.tab,
      }))
    : null

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
        <NavLink to="/" end onClick={onNavClick} className={({ isActive }) => `sidebar-nav-item${isActive ? ' active' : ''}`}>
          <span>🏠</span>
          <span>Home</span>
        </NavLink>

        {isMobile ? (
          <ExpandableNavItem emoji="🏆" label="League" isActive={isLeague} subItems={leagueSubItems} onNavClick={onNavClick} />
        ) : (
          <div>
            <NavLink to="/league" onClick={onNavClick} className={({ isActive }) => `sidebar-nav-item${isActive ? ' active' : ''}`}>
              <span>🏆</span>
              <span>League</span>
            </NavLink>
            {showLeagueSubsDesktop && (
              <div>
                {LEAGUE_SUBS.map(sub => (
                  <Link
                    key={sub.tab}
                    to={`/league?tab=${sub.tab}`}
                    onClick={onNavClick}
                    className={`sidebar-sub-item${activeLeagueTab === sub.tab ? ' active' : ''}`}
                  >
                    <span>{sub.emoji}</span>
                    <span>{sub.label}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}

        {isMobile && currentOwnerName ? (
          <ExpandableNavItem emoji="👤" label="Owners" isActive={true} subItems={ownerSubItems} onNavClick={onNavClick} />
        ) : (
          <NavLink to="/owner" onClick={onNavClick} className={({ isActive }) => `sidebar-nav-item${isActive ? ' active' : ''}`}>
            <span>👤</span>
            <span>Owners</span>
          </NavLink>
        )}

        {isMobile ? (
          <ExpandableNavItem emoji="🔄" label="Transactions" isActive={isTransactions} subItems={txnSubItems} onNavClick={onNavClick} />
        ) : (
          <NavLink to="/transactions" onClick={onNavClick} className={({ isActive }) => `sidebar-nav-item${isActive ? ' active' : ''}`}>
            <span>🔄</span>
            <span>Transactions</span>
          </NavLink>
        )}
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
        <SidebarContent onNavClick={close} isMobile />
      </div>
    </>
  )
}
