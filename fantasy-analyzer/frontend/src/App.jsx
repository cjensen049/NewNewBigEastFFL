import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Home from './pages/Home'
import League from './pages/League'
import Owner from './pages/Owner'
import OwnerRoster from './pages/OwnerRoster'
import Transactions from './pages/Transactions'
import Calendar from './pages/Calendar'

export default function App() {
  return (
    <BrowserRouter>
      <Sidebar />
      {/* All page content is offset right on desktop to clear the fixed sidebar */}
      <div className="content-with-sidebar">
        <main>
          <Routes>
            <Route path="/"             element={<Home />} />
            <Route path="/league"       element={<League />} />
            <Route path="/owner"         element={<OwnerRoster />} />
            <Route path="/owner/:name"   element={<Owner />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/calendar"     element={<Calendar />} />
            <Route path="/history"   element={<Navigate to="/league" replace />} />
            <Route path="/in-season" element={<Navigate to="/league" replace />} />
            <Route path="/h2h"       element={<Navigate to="/league" replace />} />
            <Route path="/draft"     element={<Navigate to="/league" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
