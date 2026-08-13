import { columnLetter, parseCsv } from '../utils/csv'

/** Renders CSV as an actual spreadsheet grid — lettered columns, numbered rows, a frozen
 * header row and row-number column — the way a desktop spreadsheet app (Excel, Numbers,
 * Google Sheets) shows a .csv file, instead of a raw comma-separated text dump. */
export default function SpreadsheetView({ source }: { source: string }) {
  const rows = parseCsv(source.trim())
  if (rows.length === 0) {
    return <p className="muted">No rows.</p>
  }
  const [header, ...body] = rows
  const columnCount = Math.max(header.length, ...body.map((row) => row.length))

  return (
    <div className="spreadsheet-view">
      <table className="spreadsheet-table">
        <thead>
          <tr>
            <th className="spreadsheet-row-head" aria-hidden="true" />
            {Array.from({ length: columnCount }).map((_, i) => (
              <th key={i}>{columnLetter(i)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="spreadsheet-header-row">
            <td className="spreadsheet-row-head">1</td>
            {header.map((cell, i) => (
              <td key={i} title={cell}>
                {cell}
              </td>
            ))}
          </tr>
          {body.map((row, r) => (
            <tr key={r}>
              <td className="spreadsheet-row-head">{r + 2}</td>
              {row.map((cell, c) => (
                <td key={c} title={cell}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
