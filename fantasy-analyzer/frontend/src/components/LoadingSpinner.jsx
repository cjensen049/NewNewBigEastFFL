/**
 * LoadingSpinner.jsx — centered spinner shown while data is loading.
 * Usage: <LoadingSpinner /> or <LoadingSpinner message="Fetching trades..." />
 */
export default function LoadingSpinner({ message = 'Loading...' }) {
  return (
    <div className="flex items-center justify-center py-16 text-gray-400">
      <div className="animate-spin rounded-full h-6 w-6 border-2 border-gray-600 border-t-emerald-500 mr-3" />
      <span>{message}</span>
    </div>
  )
}
