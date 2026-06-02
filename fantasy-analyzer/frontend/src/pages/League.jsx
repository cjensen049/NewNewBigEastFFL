import { useState } from 'react'
import { TabPanel } from '../components/Tabs'
import History from './History'
import InSeason from './InSeason'
import HeadToHead from './HeadToHead'
import Draft from './Draft'

const TABS = [
  { id: 'history',  label: '📊 History' },
  { id: 'inseason', label: '🏈 In-Season' },
  { id: 'h2h',      label: '⚔️ Head-to-Head' },
  { id: 'draft',    label: '📋 Draft' },
]

const CONTAINER = { maxWidth: '1280px', margin: '0 auto', padding: '0 24px' }

export default function League() {
  const [tab, setTab] = useState('history')

  return (
    <div>
      {/* Full-width header */}
      <div style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
        <div style={{ ...CONTAINER, padding: '20px 24px 0' }}>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '36px', letterSpacing: '2px', color: 'var(--text-primary)', lineHeight: 1, marginBottom: '4px' }}>
            League
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '12px' }}>
            All-time standings, records, matchups, luck, and draft history.
          </p>
          {/* Tab bar — flush to bottom of header */}
          <div style={{ display: 'flex', marginBottom: '-1px', overflowX: 'auto' }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} className={`owner-tab${tab === t.id ? ' active' : ''}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab content */}
      <div style={{ ...CONTAINER, padding: '24px 24px' }}>
        <TabPanel id="history"  activeTab={tab}><History    embedded /></TabPanel>
        <TabPanel id="inseason" activeTab={tab}><InSeason   embedded /></TabPanel>
        <TabPanel id="h2h"      activeTab={tab}><HeadToHead embedded /></TabPanel>
        <TabPanel id="draft"    activeTab={tab}><Draft      embedded /></TabPanel>
      </div>
    </div>
  )
}
