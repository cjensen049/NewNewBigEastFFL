/**
 * Tabs.jsx — tab navigation components used across all pages.
 *
 * TabBar  — desktop: horizontal tab row with brand-red underline active state.
 *           mobile: styled dropdown selector labeled "VIEW".
 * TabPanel — renders children only when its tab is active.
 */

export function TabBar({ tabs, activeTab, onChange }) {
  return (
    <>
      {/* Desktop: horizontal tab bar */}
      <div className="hidden md:flex" style={{ borderBottom: '1px solid var(--border)', marginBottom: '24px', overflowX: 'auto' }}>
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

      {/* Mobile: dropdown */}
      <div className="flex flex-col md:hidden" style={{ marginBottom: '20px' }}>
        <p style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '6px' }}>VIEW</p>
        <select
          value={activeTab}
          onChange={e => onChange(e.target.value)}
          style={{ background: 'var(--border)', border: '1px solid var(--border-mid)', color: 'var(--text-primary)', borderRadius: '6px', padding: '6px 10px', fontSize: '13px', width: '100%', fontFamily: 'var(--font-body)' }}
        >
          {tabs.map(tab => (
            <option key={tab.id} value={tab.id}>{tab.label}</option>
          ))}
        </select>
      </div>
    </>
  )
}

export function TabPanel({ id, activeTab, children }) {
  if (id !== activeTab) return null
  return <div>{children}</div>
}
