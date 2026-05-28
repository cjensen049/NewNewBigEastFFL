/**
 * main.jsx — application entry point.
 *
 * Sets up two providers that every component in the app can use:
 *   - QueryClientProvider: caches API responses so the app doesn't re-fetch
 *     the same data every time you switch tabs.
 *   - (routing is set up inside App.jsx with BrowserRouter)
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

// Create the query client with sensible defaults:
//   staleTime: data is considered fresh for 5 minutes before re-fetching
//   retry: try failed requests twice before showing an error
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 2,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
