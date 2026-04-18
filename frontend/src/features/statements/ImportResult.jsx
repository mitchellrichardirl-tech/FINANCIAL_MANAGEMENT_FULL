import { useTransactions } from '@/features/transactions/hooks';

export default function ImportResult({ result, onUploadAnother, showHeader = true }) {
  const filters = result?.upload_id
    ? { upload_id: result.upload_id, limit: 500 }
    : null;
  const txnQuery = useTransactions(filters);

  const transactions = txnQuery.data;
  const loading = txnQuery.isLoading;
  const error = txnQuery.error ? 'Failed to load transactions' : null;

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    const d = new Date(dateString);
    const day = d.getDate().toString().padStart(2, '0');
    const month = (d.getMonth() + 1).toString().padStart(2, '0');
    return `${day}-${month}-${d.getFullYear()}`;
  };

  if (!result) return null;

  const totalIncome = transactions
    ? transactions.filter((t) => t.amount > 0).reduce((s, t) => s + parseFloat(t.amount), 0)
    : 0;
  const totalExpenses = transactions
    ? Math.abs(transactions.filter((t) => t.amount < 0).reduce((s, t) => s + parseFloat(t.amount), 0))
    : 0;
  const categorizedCount = transactions ? transactions.filter((t) => t.party_id).length : 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {showHeader && (
        <div className="shrink-0 flex justify-between items-start mb-4 gap-5">
          <div className="flex-1 py-4 px-5 bg-[#d4edda] border border-[#c3e6cb] rounded">
            <h2 className="m-0 mb-2 text-lg font-semibold text-[#155724]">✓ Import Successful!</h2>
            <div className="flex items-center gap-3 text-[13px] flex-wrap">
              <span className="flex items-center gap-1.5">
                <span className="text-[#155724] font-medium">File:</span>
                <span className="text-[#155724]">{result.file_name}</span>
              </span>
              <span className="text-[#a3cfbb]">|</span>
              <span className="flex items-center gap-1.5">
                <span className="text-[#155724] font-medium">Rows:</span>
                <span className="text-[#155724]">{result.rows_imported}</span>
              </span>
              <span className="text-[#a3cfbb]">|</span>
              <span className="flex items-center gap-1.5">
                <span className="text-[#155724] font-medium">Upload ID:</span>
                <span className="text-[#155724]">{result.upload_id}</span>
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onUploadAnother}
            className="shrink-0 py-2.5 px-5 bg-[#2196f3] text-white border-0 rounded text-sm font-medium cursor-pointer hover:bg-[#1976d2]"
          >
            Upload Another File
          </button>
        </div>
      )}

      {loading && (
        <div className="text-center py-10 text-[#1976d2] text-base">Loading transactions...</div>
      )}
      {error && (
        <div className="py-3 px-4 bg-[#f8d7da] border border-[#f5c6cb] rounded text-[#721c24] mb-4">
          {error}
        </div>
      )}

      {transactions && !loading && (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          <div className="shrink-0 flex justify-between items-center mb-3">
            <h3 className="m-0 text-base font-semibold text-[#333]">Imported Transactions</h3>
            <span className="text-[13px] text-[#666]">{transactions.length} transactions</span>
          </div>
          <div className="flex-1 min-h-0 overflow-auto border border-[#dee2e6] rounded bg-white">
            <table className="w-full border-collapse text-[13px] font-sans">
              <thead>
                <tr>
                  {['Date', 'Description', 'Amount', 'Party', 'Category', 'Type'].map((h, i) => (
                    <th
                      key={h}
                      className={`sticky top-0 bg-[#f8f9fa] border-b-2 border-[#dee2e6] py-2.5 px-3 font-semibold text-[#495057] whitespace-nowrap z-[1] ${i === 2 ? 'text-right' : 'text-left'}`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr
                    key={txn.id}
                    className="even:bg-[#f8f9fa] hover:bg-[#e9ecef]"
                  >
                    <td className="py-2 px-3 border-b border-[#e9ecef] w-[90px] whitespace-nowrap">
                      {formatDate(txn.transaction_date)}
                    </td>
                    <td
                      className="py-2 px-3 border-b border-[#e9ecef] max-w-[250px] overflow-hidden text-ellipsis whitespace-nowrap"
                      title={txn.description}
                    >
                      {txn.description}
                    </td>
                    <td
                      className={`py-2 px-3 border-b border-[#e9ecef] w-[100px] text-right whitespace-nowrap font-semibold ${txn.amount > 0 ? 'text-[#28a745]' : 'text-[#dc3545]'}`}
                    >
                      €{Math.abs(parseFloat(txn.amount)).toFixed(2)}
                      <span className="ml-1 text-[11px]">{txn.amount > 0 ? '↑' : '↓'}</span>
                    </td>
                    <td className="py-2 px-3 border-b border-[#e9ecef] max-w-[120px] overflow-hidden text-ellipsis whitespace-nowrap">
                      {txn.party_name || '-'}
                    </td>
                    <td className="py-2 px-3 border-b border-[#e9ecef] max-w-[180px] overflow-hidden text-ellipsis whitespace-nowrap">
                      {txn.category_name ? (
                        <>
                          {txn.category_name}
                          {txn.sub_category_name && (
                            <span className="text-[11px] text-[#666]"> → {txn.sub_category_name}</span>
                          )}
                        </>
                      ) : '-'}
                    </td>
                    <td className="py-2 px-3 border-b border-[#e9ecef] max-w-[120px] overflow-hidden text-ellipsis whitespace-nowrap">
                      {txn.type_name || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="shrink-0 mt-4 py-4 px-5 bg-[#f8f9fa] rounded border border-[#e9ecef]">
            <h4 className="m-0 mb-3 text-sm font-semibold text-[#333]">Summary</h4>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-5">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[#666] font-medium">Total Income</span>
                <span className="text-lg font-bold text-[#28a745]">€{totalIncome.toFixed(2)}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[#666] font-medium">Total Expenses</span>
                <span className="text-lg font-bold text-[#dc3545]">€{totalExpenses.toFixed(2)}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[#666] font-medium">Categorized</span>
                <span className="text-lg font-bold text-[#333]">
                  {categorizedCount} / {transactions.length}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
