import { useState, useMemo } from 'react'

/**
 * useSortableTable — adds click-to-sort to any array of row objects.
 *
 * Returns { sorted, sortKey, sortDir, handleSort } where:
 *   sorted     — a new sorted array (never mutates the original)
 *   sortKey    — the column key currently sorted, or null
 *   sortDir    — 'asc' | 'desc'
 *   handleSort — call with a column key; toggles dir if already sorted by that key
 *
 * Numeric strings are compared as numbers; everything else is compared as strings.
 */
export function useSortableTable(rows, defaultKey = null, defaultDir = 'asc') {
  const [sortKey, setSortKey] = useState(defaultKey)
  const [sortDir, setSortDir] = useState(defaultDir)

  const sorted = useMemo(() => {
    if (!sortKey || !rows) return rows ?? []
    return [...rows].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      const an = parseFloat(av)
      const bn = parseFloat(bv)
      const cmp = !isNaN(an) && !isNaN(bn)
        ? an - bn
        : String(av ?? '').localeCompare(String(bv ?? ''), undefined, { numeric: true })
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [rows, sortKey, sortDir])

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  return { sorted, sortKey, sortDir, handleSort }
}
