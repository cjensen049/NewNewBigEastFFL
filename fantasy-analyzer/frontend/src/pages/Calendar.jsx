/**
 * Calendar.jsx — League event timeline.
 *
 * Shows each season's key milestones (draft, regular season, playoffs,
 * championship) in a vertical timeline, newest season first.
 *
 * Events are grouped by season. Each event card shows its type icon,
 * title, date range, and a status badge (complete / active / upcoming).
 */
import { useQuery } from '@tanstack/react-query'

// ─── Event type config ────────────────────────────────────────────────────────

const EVENT_CONFIG = {
  draft: {
    icon: '📋',
    label: 'Draft',
    color: 'border-l-violet-500',
    badge: { complete: 'bg-gray-700 text-gray-300', drafting: 'bg-emerald-700 text-white', upcoming: 'bg-gray-800 text-gray-400' },
  },
  regular_season: {
    icon: '🏈',
    label: 'Regular Season',
    color: 'border-l-blue-500',
    badge: { complete: 'bg-gray-700 text-gray-300', active: 'bg-blue-700 text-white', upcoming: 'bg-gray-800 text-gray-400' },
  },
  playoffs: {
    icon: '⚔️',
    label: 'Playoffs',
    color: 'border-l-orange-500',
    badge: { complete: 'bg-gray-700 text-gray-300', active: 'bg-orange-700 text-white', upcoming: 'bg-gray-800 text-gray-400' },
  },
  championship: {
    icon: '🏆',
    label: 'Championship',
    color: 'border-l-yellow-500',
    badge: { complete: 'bg-gray-700 text-gray-300', active: 'bg-yellow-700 text-white', upcoming: 'bg-gray-800 text-gray-400' },
  },
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ type, status }) {
  const config = EVENT_CONFIG[type]
  if (!config) return null
  const badgeClass = config.badge[status] ?? 'bg-gray-800 text-gray-500'
  const label = status === 'drafting' ? 'In Progress' : status.charAt(0).toUpperCase() + status.slice(1)
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${badgeClass}`}>
      {label}
    </span>
  )
}

// ─── Single event card ────────────────────────────────────────────────────────

function EventCard({ event }) {
  const config = EVENT_CONFIG[event.type] ?? { icon: '📅', color: 'border-l-gray-500' }
  const isActive = event.status === 'active' || event.status === 'drafting'

  return (
    <div className={`flex items-start gap-4 pl-4 border-l-4 ${config.color} py-3 ${
      isActive ? 'bg-gray-800/60 rounded-r' : ''
    }`}>
      {/* Icon */}
      <span className="text-xl shrink-0 leading-none mt-0.5">{config.icon}</span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-0.5">
          <span className={`font-semibold text-sm ${isActive ? 'text-white' : 'text-gray-200'}`}>
            {event.title}
          </span>
          <StatusBadge type={event.type} status={event.status} />
        </div>
        <div className="text-xs text-gray-400">
          {event.subtitle}
          {event.date_start_fmt && (
            <span className="ml-2 text-gray-500">
              · {event.date_start_fmt}
              {event.date_end_fmt && event.date_end_fmt !== event.date_start_fmt
                ? ` – ${event.date_end_fmt}`
                : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Season group ─────────────────────────────────────────────────────────────

function SeasonGroup({ season, events }) {
  const hasActive = events.some(e => e.status === 'active' || e.status === 'drafting')

  return (
    <div className="mb-8">
      {/* Season header */}
      <div className="flex items-center gap-3 mb-3">
        <h2 className={`text-lg font-bold ${hasActive ? 'text-emerald-400' : 'text-gray-300'}`}>
          {season} Season
        </h2>
        {hasActive && (
          <span className="text-xs bg-emerald-800 text-emerald-300 px-2 py-0.5 rounded font-medium">
            Current
          </span>
        )}
      </div>

      {/* Events for this season */}
      <div className="space-y-1 ml-2">
        {events.map((event, i) => (
          <EventCard key={i} event={event} />
        ))}
      </div>
    </div>
  )
}

// ─── Page root ────────────────────────────────────────────────────────────────

export default function Calendar() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['calendar-events'],
    queryFn: () => fetch('/api/calendar/events').then(r => r.json()),
  })

  if (isLoading) return <div className="text-gray-400">Loading calendar…</div>
  if (error) return <div className="text-red-400">Error loading calendar.</div>

  const events = data?.events ?? []

  // Group events by season (preserving order — newest season first)
  const bySeason = {}
  const seasonOrder = []
  events.forEach(e => {
    if (!bySeason[e.season]) {
      bySeason[e.season] = []
      seasonOrder.push(e.season)
    }
    bySeason[e.season].push(e)
  })

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-2">League Calendar</h1>
      <p className="text-gray-500 text-sm mb-8">
        Season milestones, drafts, and playoff schedules for all NNBE seasons.
      </p>

      {seasonOrder.map(season => (
        <SeasonGroup
          key={season}
          season={season}
          events={bySeason[season]}
        />
      ))}
    </div>
  )
}
