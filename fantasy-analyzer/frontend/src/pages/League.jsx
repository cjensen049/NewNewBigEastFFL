/**
 * League.jsx — wraps History, In-Season, Head-to-Head, and Draft pages.
 *
 * Tab state lives in the URL query param `?tab=history` so the global sidebar
 * sub-items can link directly to each section.
 *
 * Desktop: sidebar sub-items in the global Sidebar drive navigation.
 * Mobile: horizontal pill scroller at the top of the content area.
 */
import { useSearchParams } from 'react-router-dom'
import { TabPanel } from '../components/Tabs'
import History from './History'
import InSeason from './InSeason'
import HeadToHead from './HeadToHead'
import Draft from './Draft'
import Schedule from './Schedule'
import PowerRankingsTab from './PowerRankingsTab'

const TABS = [
  { id: 'inseason',  label: '📅 In-Season' },
  { id: 'rankings',  label: '🏆 Power Rankings' },
  { id: 'history',   label: '📊 History' },
  { id: 'h2h',       label: '⚔️ Head-to-Head' },
  { id: 'draft',     label: '📋 Draft' },
  { id: 'schedule',  label: '🗓 Schedule' },
]

export default function League() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'inseason'

  return (
    <div>
      {/* Mobile pill row — hidden at md+ (desktop uses the global sidebar) */}
      <div className="league-mobile-pills md:hidden" style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setSearchParams({ tab: t.id })}
            style={{
              display: 'inline-block',
              padding: '6px 16px',
              borderRadius: '20px',
              fontSize: '13px',
              fontWeight: 500,
              marginRight: '8px',
              cursor: 'pointer',
              border: tab === t.id ? 'none' : '1px solid var(--border)',
              background: tab === t.id ? 'var(--brand-red)' : 'var(--bg-surface)',
              color: tab === t.id ? '#ffffff' : 'var(--text-muted)',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Page content */}
      <div style={{ padding: '24px clamp(12px, 3vw, 24px)' }}>
        <TabPanel id="inseason"  activeTab={tab}><InSeason         embedded /></TabPanel>
        <TabPanel id="rankings"  activeTab={tab}><PowerRankingsTab /></TabPanel>
        <TabPanel id="history"   activeTab={tab}><History          embedded /></TabPanel>
        <TabPanel id="h2h"       activeTab={tab}><HeadToHead       embedded /></TabPanel>
        <TabPanel id="draft"     activeTab={tab}><Draft            embedded /></TabPanel>
        <TabPanel id="schedule"  activeTab={tab}><Schedule         embedded /></TabPanel>
      </div>
    </div>
  )
}
