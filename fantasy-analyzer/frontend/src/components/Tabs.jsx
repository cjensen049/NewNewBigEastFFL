/**
 * Tabs.jsx — simple tab navigation components.
 *
 * Two exports:
 *   TabBar   — the row of clickable tab buttons
 *   TabPanel — a container that only renders its children when its tab is active
 *
 * Usage:
 *   import { useState } from 'react'
 *   import { TabBar, TabPanel } from '../components/Tabs'
 *
 *   const [tab, setTab] = useState('standings')
 *
 *   <TabBar
 *     tabs={[
 *       { id: 'standings', label: 'Standings' },
 *       { id: 'records',   label: 'Records' },
 *     ]}
 *     activeTab={tab}
 *     onChange={setTab}
 *   />
 *   <TabPanel id="standings" activeTab={tab}>
 *     <p>Standings content here</p>
 *   </TabPanel>
 *   <TabPanel id="records" activeTab={tab}>
 *     <p>Records content here</p>
 *   </TabPanel>
 */

export function TabBar({ tabs, activeTab, onChange }) {
  return (
    <div className="flex border-b border-gray-700 mb-6 overflow-x-auto">
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={[
            'px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors -mb-px',
            activeTab === tab.id
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-gray-400 hover:text-gray-200',
          ].join(' ')}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

// Only renders children when this panel's id matches the active tab
export function TabPanel({ id, activeTab, children }) {
  if (id !== activeTab) return null
  return <div>{children}</div>
}
