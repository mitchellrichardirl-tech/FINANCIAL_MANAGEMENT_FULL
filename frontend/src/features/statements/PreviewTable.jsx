function PreviewTable({ previewData, startRow }) {
  if (!previewData) return null;
  const { columns, data, column_types } = previewData;

  if (!columns || !data) {
    return (
      <div className="p-5 text-red-600">
        <p>Invalid preview data structure</p>
        <pre>{JSON.stringify(previewData, null, 2)}</pre>
      </div>
    );
  }

  const ROW_OFFSET = 1;

  const rowBg = (n) => {
    if (n === startRow) return 'bg-[#fff3cd]';
    if (n < startRow) return 'bg-[#f8d7da] opacity-60';
    return 'bg-white';
  };

  return (
    <div className="p-4 h-full flex flex-col overflow-hidden">
      <h2 className="m-0 mb-4 shrink-0 text-xl font-bold">File Preview</h2>

      <div className="py-[10px] px-4 bg-[#e7f3ff] border-l-4 border-[#4a90e2] mb-4 text-[13px] text-[#333] shrink-0">
        <div className="mb-2">
          <strong>Note:</strong> Preview shows rows 2 onwards (row 1 was used as column headers).
        </div>
        <div className="flex gap-5 flex-wrap">
          {[
            ['Rows to skip', '#f8d7da'],
            ['Header row', '#fff3cd'],
            ['Data rows', '#ffffff'],
          ].map(([label, color]) => (
            <div key={label} className="flex items-center">
              <div
                className="w-4 h-4 border border-[#dee2e6] mr-1.5"
                style={{ backgroundColor: color }}
              />
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto border border-[#dee2e6] rounded">
        <table className="w-full border-collapse bg-white">
          <thead>
            <tr className="bg-[#f8f9fa]">
              <th className="p-3 text-left border-b-2 border-[#dee2e6] font-bold sticky top-0 bg-[#f8f9fa] z-10">
                Row
              </th>
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className="p-3 text-left border-b-2 border-[#dee2e6] font-bold sticky top-0 bg-[#f8f9fa] z-10"
                >
                  <div>{col}</div>
                  {column_types && column_types[col] && (
                    <div className="text-[11px] text-[#6c757d] font-normal mt-1">
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
                <tr key={rowIdx} className={rowBg(actualRowNum)}>
                  <td className="py-[10px] px-3 border-b border-[#dee2e6] font-bold text-[#6c757d]">
                    {actualRowNum}
                  </td>
                  {columns.map((col, colIdx) => (
                    <td key={colIdx} className="py-[10px] px-3 border-b border-[#dee2e6]">
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
