/**
 * NavBar.jsx — top navigation bar, always visible.
 *
 * NavLink from React Router automatically adds an "active" class when the
 * current URL matches the link's `to` prop. We use that to highlight the
 * active page with a green background.
 */
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/',             label: '🏠 Home',         end: true },
  { to: '/league',       label: '📊 League' },
  { to: '/owner',        label: '👤 Owners' },
  { to: '/transactions', label: '💱 Transactions' },
  { to: '/draft',        label: '📋 Draft' },
]

export default function NavBar() {
  return (
    <nav className="bg-gray-800 border-b border-gray-700">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center h-14 gap-1">
          {/* League logo + name */}
          <div className="flex items-center gap-2 mr-6 shrink-0">
            <img
              src="/logo.png"
              alt=""
              className="h-7 w-7 rounded object-contain"
              onError={e => { e.target.style.display = 'none' }}
            />
            <span className="text-emerald-400 font-bold text-lg">NNBE</span>
          </div>

          {/* Navigation links — overflow-x-auto makes them scrollable on small screens */}
          <div className="flex overflow-x-auto gap-1">
            {links.map(link => (
              <NavLink
                key={link.to}
                to={link.to}
                end={!!link.end}
                className={({ isActive }) =>
                  `px-3 py-2 text-sm rounded whitespace-nowrap transition-colors ${
                    isActive
                      ? 'bg-emerald-700 text-white font-medium'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
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
