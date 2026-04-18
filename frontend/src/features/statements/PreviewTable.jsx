/**
 * @file PreviewTable.jsx
 * Read-only table showing the first N rows of a statement file before
 * import.
 *
 * Rows are colour-coded:
 *  - **Red (skipped)** — rows before `startRow`.
 *  - **Yellow (header)** — the row at `startRow` (first data row).
 *  - **White (data)** — rows after `startRow`.
 *
 * Column headers show the inferred type (string/number/date) when
 * provided by the backend.
 */

/**
 * File preview table.
 *
 * @component
 * @param {Object} props
 *
 * @param {Object} props.previewData
 *        Response from `/tabular/preview`. Expected shape:
 *        `{ columns: string[], data: Object[], total_rows: number, column_types?: Record<string,string> }`.
 * @param {number} props.startRow
 *        1-based index of the first data row (rows before are skipped).
 * @param {(row: number) => void} props.onStartRowChange
 *        (Currently unused in this component — change is handled by the
 *        parent's `<input>`.) Included for parity if clicking a row
 *        should set the start row in the future.
 * @param {boolean} [props.compact]
 *        Unused — kept for API consistency.
 *
 * @returns {JSX.Element|null}
 */
function PreviewTable({ previewData, startRow, onStartRowChange }) {
  if (!previewData) return null;

  const { columns, data, total_rows, column_types } = previewData;

  if (!columns || !data) {
    return (
      <div className="p-[20px] text-red-600">
        <p>Invalid preview data structure</p>
        <pre>{JSON.stringify(previewData, null, 2)}</pre>
      </div>
    );
  }

  /**
   * Preview rows are 0-indexed, but the original file's row 1 is the
   * header (used as `columns`), so data[0] corresponds to file row 2.
   */
  const ROW_OFFSET = 1;

  return (
    <div className="p-[15px] h-full flex flex-col overflow-hidden">
      <h2 className="m-[0_0_15px_0] shrink-0">File Preview</h2>

      {/* Legend */}
      <div className="p-[10px_15px] bg-[#e7f3ff] border-l-[4px] border-l-[#4a90e2] mb-[15px] text-[13px] text-text-dark shrink-0">
        <div className="mb-[8px]">
          <strong>Note:</strong> Preview shows rows 2 onwards (row 1 was used as column headers).
        </div>
        <div className="flex gap-[20px] flex-wrap">
          <div className="flex items-center">
            <div className="w-[16px] h-[16px] bg-[#f8d7da] border border-[#dee2e6] mr-[6px]"></div>
            <span>Rows to skip</span>
          </div>
          <div className="flex items-center">
            <div className="w-[16px] h-[16px] bg-[#fff3cd] border border-[#dee2e6] mr-[6px]"></div>
            <span>Header row</span>
          </div>
          <div className="flex items-center">
            <div className="w-[16px] h-[16px] bg-white border border-[#dee2e6] mr-[6px]"></div>
            <span>Data rows</span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto border border-[#dee2e6] rounded-[4px]">
        <table className="w-full border-collapse bg-white">
          <thead>
            <tr className="bg-[#f8f9fa]">
              <th className="p-[12px] text-left border-b-2 border-[#dee2e6] font-bold sticky top-0 bg-[#f8f9fa] z-10">
                Row
              </th>
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className="p-[12px] text-left border-b-2 border-[#dee2e6] font-bold sticky top-0 bg-[#f8f9fa] z-10"
                >
                  <div>{col}</div>
                  {column_types && column_types[col] && (
                    <div className="text-[11px] text-[#6c757d] font-normal mt-[4px]">
                      {column_types[col]}
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIdx) => {
              const actualRowNum = rowIdx + ROW_OFFSET + 1;
              return (
                <tr
                  key={rowIdx}
                  style={{
                    backgroundColor:
                      actualRowNum === startRow
                        ? '#fff3cd'
                        : actualRowNum < startRow
                        ? '#f8d7da'
                        : 'white',
                    opacity: actualRowNum < startRow ? 0.6 : 1,
                  }}
                >
                  <td className="p-[10px_12px] border-b border-[#dee2e6] font-bold text-[#6c757d]">
                    {actualRowNum}
                  </td>
                  {columns.map((col, colIdx) => (
                    <td
                      key={colIdx}
                      className="p-[10px_12px] border-b border-[#dee2e6]"
                    >
                      {row[col] !== null && row[col] !== undefined ? String(row[col]) : ''}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PreviewTable;
