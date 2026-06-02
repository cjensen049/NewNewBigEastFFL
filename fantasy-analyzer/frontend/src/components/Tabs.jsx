/**
 * Tabs.jsx — tab navigation components used across all pages.
 *
 * TabBar  — row of clickable tab buttons (active state uses brand-red underline)
 * TabPanel — renders children only when its tab is active
 */

export function TabBar({ tabs, activeTab, onChange }) {
  return (
    <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: '24px', overflowX: 'auto' }}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`owner-tab${activeTab === tab.id ? ' active' : ''}`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export function TabPanel({ id, activeTab, children }) {
  if (id !== activeTab) return null
  return <div>{children}</div>
}
