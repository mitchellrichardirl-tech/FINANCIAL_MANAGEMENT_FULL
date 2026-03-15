function PreviewTable({ previewData, startRow, onStartRowChange }) {
  if (!previewData) return null;

  const { columns, data, total_rows, column_types } = previewData;

  if (!columns || !data) {
    return (
      <div style={{ padding: '20px', color: 'red' }}>
        <p>Invalid preview data structure</p>
        <pre>{JSON.stringify(previewData, null, 2)}</pre>
      </div>
    );
  }

  const ROW_OFFSET = 1; // Because data starts from row 2 (row 1 is headers)

  return (
    <div style={{ 
      padding: '15px', 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column',
      overflow: 'hidden'           // Prevents outer scroll
    }}>
      <h2 style={{ margin: '0 0 15px 0', flexShrink: 0 }}>File Preview</h2>
      
      {/* Info box - prevent shrinking */}
      <div style={{ 
        padding: '10px 15px', 
        backgroundColor: '#e7f3ff', 
        borderLeft: '4px solid #4a90e2',
        marginBottom: '15px',
        fontSize: '13px',
        color: '#333',
        flexShrink: 0
      }}>
        <div style={{ marginBottom: '8px' }}>
          <strong>Note:</strong> Preview shows rows 2 onwards (row 1 was used as column headers).
        </div>
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              width: '16px',
              height: '16px',
              backgroundColor: '#f8d7da',
              border: '1px solid #dee2e6',
              marginRight: '6px'
            }}></div>
            <span>Rows to skip</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              width: '16px',
              height: '16px',
              backgroundColor: '#fff3cd',
              border: '1px solid #dee2e6',
              marginRight: '6px'
            }}></div>
            <span>Header row</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              width: '16px',
              height: '16px',
              backgroundColor: 'white',
              border: '1px solid #dee2e6',
              marginRight: '6px'
            }}></div>
            <span>Data rows</span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div style={{ 
        flex: 1, 
        minHeight: 0,
        overflowY: 'auto', 
        overflowX: 'auto', 
        border: '1px solid #dee2e6', 
        borderRadius: '4px' 
      }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          backgroundColor: 'white'
        }}>
          <thead>
            <tr style={{ backgroundColor: '#f8f9fa' }}>
              <th style={{
                padding: '12px',
                textAlign: 'left',
                borderBottom: '2px solid #dee2e6',
                fontWeight: 'bold',
                position: 'sticky',
                top: 0,
                backgroundColor: '#f8f9fa',
                zIndex: 10
              }}>
                Row
              </th>
              {columns.map((col, idx) => (
                <th key={idx} style={{
                  padding: '12px',
                  textAlign: 'left',
                  borderBottom: '2px solid #dee2e6',
                  fontWeight: 'bold',
                  position: 'sticky',
                  top: 0,
                  backgroundColor: '#f8f9fa',
                  zIndex: 10
                }}>
                  <div>{col}</div>
                  {column_types && column_types[col] && (
                    <div style={{ 
                      fontSize: '11px', 
                      color: '#6c757d',
                      fontWeight: 'normal',
                      marginTop: '4px'
                    }}>
                      {column_types[col]}
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIdx) => {
              // This row is actually row (rowIdx + 2) in the original file
              const actualRowNum = rowIdx + ROW_OFFSET + 1;
              return (
                <tr key={rowIdx} style={{
                  backgroundColor: actualRowNum === startRow 
                    ? '#fff3cd' 
                    : actualRowNum < startRow 
                      ? '#f8d7da' 
                      : 'white',
                  opacity: actualRowNum < startRow ? 0.6 : 1
                }}>
                  <td style={{
                    padding: '10px 12px',
                    borderBottom: '1px solid #dee2e6',
                    fontWeight: 'bold',
                    color: '#6c757d'
                  }}>
                    {actualRowNum}
                  </td>
                  {columns.map((col, colIdx) => (
                    <td key={colIdx} style={{
                      padding: '10px 12px',
                      borderBottom: '1px solid #dee2e6'
                    }}>
                      {row[col] !== null && row[col] !== undefined 
                        ? String(row[col]) 
                        : ''}
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