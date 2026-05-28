/**
 * App.jsx — top-level routing and layout.
 *
 * BrowserRouter enables URL-based navigation (e.g. /history, /owner).
 * Routes maps each URL path to a page component.
 * NavBar renders the top navigation and is always visible.
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './components/NavBar'
import History from './pages/History'
import Owner from './pages/Owner'
import HeadToHead from './pages/HeadToHead'
import Transactions from './pages/Transactions'
import InSeason from './pages/InSeason'

export default function App() {
  return (
    <BrowserRouter>
      {/* Dark background covers the whole page */}
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <NavBar />
        {/* max-w-7xl keeps content readable on wide monitors */}
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Routes>
            {/* Redirect the root URL to /history */}
            <Route path="/" element={<Navigate to="/history" replace />} />
            <Route path="/history" element={<History />} />
            <Route path="/owner" element={<Owner />} />
            <Route path="/h2h" element={<HeadToHead />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/in-season" element={<InSeason />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
