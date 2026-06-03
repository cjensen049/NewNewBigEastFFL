/**
 * DataTable.jsx — a scrollable table rendered from an array of row objects.
 *
 * Props:
 *   rows     — array of plain objects (one object = one table row)
 *   columns  — array of column descriptors:
 *                { key: string,      ← matches the key in each row object
 *                  label: string,    ← column header text
 *                  align?: 'right',  ← optional right-align (default left)
 *                  render?: (value, row) => ReactNode }  ← optional custom cell renderer
 *   maxHeight — CSS string for max height of the scrollable area (default '420px')
 *
 * Example:
 *   <DataTable
 *     rows={[{ owner: 'Jensen', wins: 52 }]}
 *     columns={[
 *       { key: 'owner', label: 'Owner' },
 *       { key: 'wins',  label: 'Wins', align: 'right' },
 *     ]}
 *   />
 */
export default function DataTable({ rows, columns, maxHeight = '420px' }) {
  if (!rows || rows.length === 0) {
    return <p className="text-gray-500 text-sm py-4 italic">No data available.</p>
  }

  return (
    <div
      className="overflow-auto rounded border border-gray-700 text-sm"
      style={{ maxHeight }}
    >
      <table className="w-full text-left text-gray-300">
        <thead className="sticky top-0 bg-gray-800 text-gray-400 uppercase text-xs">
          <tr>
            {columns.map(col => (
              <th
                key={col.key}
                className={`px-3 py-2 font-medium whitespace-nowrap ${col.align === 'right' ? 'text-right' : ''}`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-gray-700/20">
              {columns.map(col => {
                const value = row[col.key]
                const display = col.render
                  ? col.render(value, row)
                  : value != null ? String(value) : '—'
                return (
                  <td
                    key={col.key}
                    className={`px-3 py-2 whitespace-nowrap ${col.align === 'right' ? 'text-right' : ''}`}
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
