import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import League from './pages/League'
import Owner from './pages/Owner'
import Transactions from './pages/Transactions'
import Calendar from './pages/Calendar'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen">
        <NavBar />
        <main>
          <Routes>
            <Route path="/"             element={<Home />} />
            <Route path="/league"       element={<League />} />
            <Route path="/owner"        element={<Owner />} />
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
