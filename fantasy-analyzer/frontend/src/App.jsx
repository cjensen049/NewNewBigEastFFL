/**
 * App.jsx — top-level routing and layout.
 *
 * BrowserRouter enables URL-based navigation (e.g. /history, /owner).
 * Routes maps each URL path to a page component.
 * NavBar renders the top navigation and is always visible.
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import League from './pages/League'
import History from './pages/History'
import Owner from './pages/Owner'
import HeadToHead from './pages/HeadToHead'
import Transactions from './pages/Transactions'
import InSeason from './pages/InSeason'
import Draft from './pages/Draft'
import Calendar from './pages/Calendar'

export default function App() {
  return (
    <BrowserRouter>
      {/* Dark background covers the whole page */}
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <NavBar />
        {/* max-w-7xl keeps content readable on wide monitors */}
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/"             element={<Home />} />
            <Route path="/league"       element={<League />} />
            <Route path="/owner"        element={<Owner />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/draft"        element={<Draft />} />
            <Route path="/calendar"     element={<Calendar />} />
            {/* Legacy redirects — old direct links still work */}
            <Route path="/history"   element={<Navigate to="/league" replace />} />
            <Route path="/in-season" element={<Navigate to="/league" replace />} />
            <Route path="/h2h"       element={<Navigate to="/league" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
