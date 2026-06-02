/**
 * League.jsx — unified "what has happened historically" page.
 *
 * Top-level tabs wrap History (standings, records, champions),
 * In-Season (luck, race to the bottom), and Head-to-Head matchups.
 * Each sub-page is passed embedded={true} to suppress its own <h1>.
 */
import { useState } from 'react'
import { TabBar, TabPanel } from '../components/Tabs'
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
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">League</h1>
      <p className="text-gray-400 text-sm mb-6">
        What has happened historically — standings, records, matchups, luck, and draft history.
      </p>

      <TabBar tabs={TABS} activeTab={tab} onChange={setTab} />

      <TabPanel id="history"  activeTab={tab}><History    embedded /></TabPanel>
      <TabPanel id="inseason" activeTab={tab}><InSeason   embedded /></TabPanel>
      <TabPanel id="h2h"      activeTab={tab}><HeadToHead embedded /></TabPanel>
      <TabPanel id="draft"    activeTab={tab}><Draft      embedded /></TabPanel>
    </div>
  )
}
