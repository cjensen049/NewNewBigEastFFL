/**
 * Home.jsx — landing page.
 *
 * Four loud nav cards (League / Owners / Transactions / Draft), a compact
 * in-season snapshot showing the current season's standings vs simulated
 * record, and a calendar widget showing this season's milestones.
 */
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import LoadingSpinner from '../components/LoadingSpinner'

// ─── Nav cards ────────────────────────────────────────────────────────────────

const NAV_CARDS = [
  {
    to: '/league',
    icon: '📊',
    title: 'League History',
    description: 'All-time standings, records, head-to-head matchups, schedule luck, in-season tools, and full draft history.',
    borderColor: 'border-l-blue-500',
  },
  {
    to: '/owner',
    icon: '👤',
    title: 'Owner Dashboard',
    description: 'Individual profiles — career summary, draft picks, trade activity, waiver trends, and nemesis/prey matchups.',
    borderColor: 'border-l-red-500',
  },
  {
    to: '/transactions',
    icon: '💱',
    title: 'Transaction History',
    description: 'Trade timelines, waiver wire activity, and transaction patterns across all seasons.',
    borderColor: 'border-l-violet-500',
  },
]

function NavCard({ to, icon, title, description, borderColor }) {
  return (
    <Link
      to={to}
      className={`block bg-gray-800 border border-gray-700 border-l-4 ${borderColor} rounded-lg p-5 hover:bg-gray-700/60 transition-colors group`}
    >
      <div className="flex items-start gap-4">
        <span className="text-3xl shrink-0 mt-0.5">{icon}</span>
        <div>
          <h3 className="text-lg font-bold text-white mb-1 group-hover:text-emerald-400 transition-colors">
            {title} →
          </h3>
          <p className="text-sm text-gray-400 leading-relaxed">{description}</p>
        </div>
      </div>
    </Link>
  )
}

// ─── In-season snapshot ───────────────────────────────────────────────────────

function InSeasonSnapshot() {
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
  if (rows.length === 0) {
    return <p className="text-gray-500 text-sm italic">No in-season data yet.</p>
  }

  const pct = v => v != null ? `${(v * 100).toFixed(1)}%` : '—'
  const nextWeek = data?.next_week
  const oppHeader = `Wk ${nextWeek ?? 1} Opp`

  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">{currentSeason} · Actual record vs simulated schedule</p>
      <div className="overflow-auto rounded border border-gray-700">
        <table className="text-xs text-gray-300">
          <thead className="bg-gray-800 text-gray-500 uppercase">
            <tr>
              <th className="px-2 py-2 text-left whitespace-nowrap">Owner</th>
              <th className="px-2 py-2 text-right whitespace-nowrap">W-L</th>
              <th className="px-2 py-2 text-right whitespace-nowrap">Sim W-L</th>
              <th className="px-2 py-2 text-right whitespace-nowrap">Diff</th>
              <th className="px-2 py-2 text-left whitespace-nowrap">Verdict</th>
              <th className="px-2 py-2 text-left whitespace-nowrap">{oppHeader}</th>
              <th className="px-2 py-2 text-right whitespace-nowrap">Rem SoS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/40">
            {rows.map((r, i) => {
              const diff = r.win_pct_diff
              const diffStr = `${diff >= 0 ? '+' : ''}${pct(diff)}`
              const diffColor = diff >= 0.1 ? 'text-emerald-400' : diff <= -0.1 ? 'text-red-400' : 'text-gray-400'
              const sos = r.remaining_sos
              const sosColor = sos == null ? 'text-gray-600'
                : sos >= 0.55 ? 'text-red-400'
                : sos <= 0.40 ? 'text-emerald-400'
                : 'text-gray-400'
              return (
                <tr key={i} className="hover:bg-gray-700/20">
                  <td className="px-2 py-1.5 font-medium whitespace-nowrap">{r.owner}</td>
                  <td className="px-2 py-1.5 text-right">{r.actual_wins}-{r.actual_losses}</td>
                  <td className="px-2 py-1.5 text-right">{r.sim_wins}-{r.sim_losses}</td>
                  <td className={`px-2 py-1.5 text-right ${diffColor}`}>{diffStr}</td>
                  <td className="px-2 py-1.5 text-gray-500">{r.verdict}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap">{r.next_opponent ?? '—'}</td>
                  <td className={`px-2 py-1.5 text-right ${sosColor}`}>{pct(sos)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3">
        <Link to="/league" className="text-xs text-emerald-400 hover:underline">
          Full standings &amp; analysis →
        </Link>
      </div>
    </div>
  )
}

// ─── Calendar widget ──────────────────────────────────────────────────────────

const TYPE_ICON = { draft: '📋', dues: '💰', roster_deadline: '📝', regular_season: '🏈', trade_deadline: '⏰', playoffs: '⚔️', championship: '🏆' }

function CalendarWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ['calendar-events'],
    queryFn: () => fetch('/api/calendar/events').then(r => r.json()),
  })

  if (isLoading) return <LoadingSpinner />

  const events = data?.events ?? []
  if (events.length === 0) return <p className="text-gray-500 text-sm">No events.</p>

  // Show the current (newest) season's events
  const currentSeason = events[0].season
  const currentEvents = events.filter(e => e.season === currentSeason)

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-semibold text-gray-200">{currentSeason} Season</span>
        <span className="text-xs bg-emerald-800 text-emerald-300 px-2 py-0.5 rounded">Current</span>
      </div>

      <div className="space-y-2.5">
        {currentEvents.map((e, i) => {
          const isActive = e.status === 'active' || e.status === 'drafting'
          const statusLabel = e.status === 'drafting' ? 'Active' : e.status.charAt(0).toUpperCase() + e.status.slice(1)
          const statusColor = isActive ? 'text-emerald-400' : e.status === 'complete' ? 'text-gray-600' : 'text-gray-500'
          return (
            <div key={i} className={`flex items-center gap-3 text-sm ${isActive ? 'bg-gray-700/30 rounded px-2 py-1' : 'px-2 py-0.5'}`}>
              <span className="text-base shrink-0">{TYPE_ICON[e.type] ?? '📅'}</span>
              <div className="flex-1 min-w-0">
                <span className={isActive ? 'text-white font-medium' : 'text-gray-300'}>{e.title}</span>
                {e.date_start_fmt && (
                  <span className="text-gray-600 text-xs ml-2">
                    {e.date_start_fmt}
                    {e.date_end_fmt && e.date_end_fmt !== e.date_start_fmt ? ` – ${e.date_end_fmt}` : ''}
                  </span>
                )}
              </div>
              <span className={`text-xs shrink-0 ${statusColor}`}>{statusLabel}</span>
            </div>
          )
        })}
      </div>

      <div className="mt-4 pt-3 border-t border-gray-700">
        <Link to="/calendar" className="text-xs text-emerald-400 hover:underline">
          View full calendar →
        </Link>
      </div>
    </div>
  )
}

// ─── Page root ────────────────────────────────────────────────────────────────

export default function Home() {
  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <img
          src="/logo.png"
          alt="NNBE"
          className="h-16 w-16 rounded-xl object-contain shrink-0"
          onError={e => { e.target.style.display = 'none' }}
        />
        <div>
          <h1 className="text-3xl font-bold text-white leading-tight">NNBE Fantasy Football</h1>
          <p className="text-gray-400 text-sm mt-1">The New New Big East — 2021 through present</p>
        </div>
      </div>

      {/* Nav cards — always stacked vertically */}
      <div className="flex flex-col gap-3 mb-10">
        {NAV_CARDS.map(card => <NavCard key={card.to} {...card} />)}
      </div>

      {/* Lower section: in-season snapshot + calendar */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-white mb-4">🏈 Current Season Snapshot</h2>
          <InSeasonSnapshot />
        </div>
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-white mb-4">📅 Season Calendar</h2>
          <CalendarWidget />
        </div>
      </div>
    </div>
  )
}
