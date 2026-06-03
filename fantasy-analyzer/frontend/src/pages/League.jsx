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

export default function League() {
  const [tab, setTab] = useState('history')

  return (
    <div style={{ display: 'flex', minHeight: 'calc(100vh - 52px)', alignItems: 'stretch' }}>

      {/* Desktop sidebar — hidden below md */}
      <div className="hidden md:flex flex-col" style={{
        width: '180px',
        flexShrink: 0,
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
      }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="league-sidebar-item"
            style={{
              borderLeft: tab === t.id ? '3px solid var(--brand-red)' : '3px solid transparent',
              background: tab === t.id ? 'var(--bg-raised)' : 'transparent',
              color: tab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Right content area */}
      <div style={{ flex: 1, minWidth: 0 }}>

        {/* Mobile pill row — hidden at md+ */}
        <div className="league-mobile-pills md:hidden" style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
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
          <TabPanel id="history"  activeTab={tab}><History    embedded /></TabPanel>
          <TabPanel id="inseason" activeTab={tab}><InSeason   embedded /></TabPanel>
          <TabPanel id="h2h"      activeTab={tab}><HeadToHead embedded /></TabPanel>
          <TabPanel id="draft"    activeTab={tab}><Draft      embedded /></TabPanel>
        </div>

      </div>
    </div>
  )
}
