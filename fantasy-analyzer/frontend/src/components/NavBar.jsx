/**
 * NavBar.jsx — top navigation bar, always visible.
 *
 * NavLink from React Router automatically adds an "active" class when the
 * current URL matches the link's `to` prop. We use that to highlight the
 * active page with a green background.
 */
import { Link, NavLink } from 'react-router-dom'

const links = [
  { to: '/league',       label: 'League' },
  { to: '/owner',        label: 'Owners' },
  { to: '/transactions', label: 'Transactions' },
]

export default function NavBar() {
  return (
    <nav className="bg-slate-950 border-t-4 border-red-600 border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center h-14 gap-1">
          {/* Clickable logo + name — takes user back to home */}
          <Link to="/" className="flex items-center gap-2 mr-6 shrink-0 group">
            <img
              src="/logo.png"
              alt="NNBE"
              className="h-8 w-8 rounded object-contain"
              onError={e => { e.target.style.display = 'none' }}
            />
            <span className="text-white font-bold text-lg tracking-wide group-hover:text-blue-300 transition-colors">
              NNBE
            </span>
          </Link>

          {/* Navigation links */}
          <div className="flex overflow-x-auto gap-1">
            {links.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `px-3 py-2 text-sm rounded whitespace-nowrap transition-colors ${
                    isActive
                      ? 'bg-blue-700 text-white font-semibold'
                      : 'text-blue-300 hover:bg-slate-800 hover:text-white'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}
