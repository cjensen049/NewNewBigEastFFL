import { Link, NavLink } from 'react-router-dom'

const links = [
  { to: '/league',       label: 'League' },
  { to: '/owner',        label: 'Owners' },
  { to: '/transactions', label: 'Transactions' },
]

export default function NavBar() {
  return (
    <nav style={{
      background: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border)',
      height: '52px',
      position: 'sticky',
      top: 0,
      zIndex: 50,
    }}>
      <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 clamp(12px, 3vw, 24px)', height: '100%', display: 'flex', alignItems: 'center', gap: '8px' }}>

        {/* Logo + wordmark */}
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '10px', marginRight: '24px', textDecoration: 'none', flexShrink: 0 }}>
          <img
            src="/logo.png"
            alt="NNBE"
            style={{ height: '32px', width: '32px', borderRadius: '4px', objectFit: 'contain' }}
            onError={e => { e.target.style.display = 'none' }}
          />
          <span style={{ fontFamily: 'var(--font-display)', fontSize: '22px', letterSpacing: '2px', lineHeight: 1 }}>
            <span style={{ color: '#f0f0f0' }}>N</span>
            <span style={{ color: '#f0f0f0' }}>N</span>
            <span style={{ color: '#cc1f2e' }}>B</span>
            <span style={{ color: '#1a3a6b' }}>E</span>
          </span>
        </Link>

        {/* Nav links */}
        <div style={{ display: 'flex', gap: '4px', overflowX: 'auto' }}>
          {links.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => `nnbe-nav-link${isActive ? ' active' : ''}`}
            >
              {link.label}
            </NavLink>
          ))}
        </div>

      </div>
    </nav>
  )
}
