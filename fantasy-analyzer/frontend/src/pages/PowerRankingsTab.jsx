/**
 * PowerRankingsTab.jsx — Power Rankings tab wrapper for the League page.
 *
 * Houses both Weekly and Dynasty power rankings behind a toggle button.
 * Weekly: current-season performance (scoring, record, SoS, roster quality).
 * Dynasty: long-term strength (roster value, draft capital, age curve).
 *
 * Props:
 *   season       {number} — active season year
 *   embedded     {boolean} — passed through; suppresses standalone page padding
 *
 * The Weekly/Dynasty toggle is stored in the `view` URL query param (alongside
 * League.jsx's `tab` param) so refreshing the page stays on whichever one was
 * active instead of reverting to Weekly.
 */
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import PowerRankings from './PowerRankings'
import DynastyRankings from './DynastyRankings'

const VIEWS = [
  { id: 'weekly',  label: '📈 Weekly',  desc: 'Current season performance' },
  { id: 'dynasty', label: '🏰 Dynasty', desc: 'Long-term roster strength'  },
]

function ToggleButton({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '7px 18px',
        borderRadius: '6px',
        fontSize: '13px',
        fontWeight: 600,
        cursor: 'pointer',
        border: active ? '1px solid transparent' : '1px solid var(--border-mid)',
        background: active ? 'var(--brand-navy)' : 'var(--border)',
        color: active ? '#ffffff' : 'var(--text-muted)',
        transition: 'background 0.15s, color 0.15s',
      }}
    >
      {label}
    </button>
  )
}

export default function PowerRankingsTab() {
  const [searchParams, setSearchParams] = useSearchParams()
  const view = searchParams.get('view') || 'weekly'
  const setView = (id) => {
    const next = new URLSearchParams(searchParams)
    next.set('view', id)
    setSearchParams(next)
  }

  const { data: seasonsData } = useQuery({
    queryKey: ['inseason-seasons'],
    queryFn: () => fetch('/api/in-season/seasons').then(r => r.json()),
  })
  const season = seasonsData?.seasons?.[0] ?? null
  const active = VIEWS.find(v => v.id === view)

  return (
    <div>
      {/* View toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
        {VIEWS.map(v => (
          <ToggleButton
            key={v.id}
            active={view === v.id}
            onClick={() => setView(v.id)}
            label={v.label}
          />
        ))}
        {active && (
          <span style={{ fontSize: '11px', color: 'var(--text-faint)', marginLeft: '4px' }}>
            {active.desc}
          </span>
        )}
      </div>

      {view === 'weekly'  && <PowerRankings   season={season} />}
      {view === 'dynasty' && <DynastyRankings season={season} />}
    </div>
  )
}
