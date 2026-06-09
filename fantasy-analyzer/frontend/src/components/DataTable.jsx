/**
 * DataTable.jsx — a scrollable, sortable table rendered from an array of row objects.
 *
 * Props:
 *   rows       — array of plain objects (one object = one table row)
 *   columns    — array of column descriptors:
 *                  { key: string,      ← matches the key in each row object
 *                    label: string,    ← column header text
 *                    align?: 'right',  ← optional right-align (default left)
 *                    sortable?: false, ← pass false to disable sort on a column (default sortable)
 *                    render?: (value, row) => ReactNode }  ← optional custom cell renderer
 *   maxHeight  — CSS string for max height of the scrollable area (default '420px')
 *   defaultSort — key of the column to sort by initially (default null = no sort)
 *   defaultDir  — 'asc' | 'desc' (default 'asc')
 *
 * Clicking a header sorts by that column; clicking again reverses direction.
 * Sort indicator: ↑ ascending, ↓ descending, no icon when unsorted.
 */
import { useSortableTable } from '../hooks/useSortableTable'

export default function DataTable({ rows, columns, maxHeight = '420px', defaultSort = null, defaultDir = 'asc' }) {
  const { sorted, sortKey, sortDir, handleSort } = useSortableTable(rows, defaultSort, defaultDir)

  if (!rows || rows.length === 0) {
    return <p style={{ color: 'var(--text-faint)', fontSize: '13px', padding: '16px 0', fontStyle: 'italic' }}>No data available.</p>
  }

  return (
    <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight, borderRadius: '8px', border: '1px solid var(--border)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '16px', textAlign: 'left' }}>
        <thead className="sticky top-0">
          <tr>
            {columns.map(col => {
              const isSorted = sortKey === col.key
              const canSort = col.sortable !== false
              return (
                <th
                  key={col.key}
                  onClick={canSort ? () => handleSort(col.key) : undefined}
                  style={{
                    padding: '8px 12px',
                    fontSize: '11px',
                    fontWeight: 600,
                    letterSpacing: '1px',
                    textTransform: 'uppercase',
                    color: isSorted ? 'var(--text-primary)' : 'var(--text-faint)',
                    background: 'var(--bg-page)',
                    textAlign: col.align === 'right' ? 'right' : 'left',
                    whiteSpace: 'nowrap',
                    cursor: canSort ? 'pointer' : 'default',
                    userSelect: 'none',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  {col.label}
                  {canSort && (
                    <span style={{ marginLeft: '4px', opacity: isSorted ? 1 : 0.35, fontSize: '9px' }}>
                      {isSorted ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
                    </span>
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={i}
              style={{ borderBottom: '1px solid var(--border)' }}
              className="standings-row"
            >
              {columns.map(col => {
                const value = row[col.key]
                const display = col.render
                  ? col.render(value, row)
                  : value != null ? String(value) : '—'
                return (
                  <td
                    key={col.key}
                    style={{
                      padding: '8px 12px',
                      color: 'var(--text-primary)',
                      textAlign: col.align === 'right' ? 'right' : 'left',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {display}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
