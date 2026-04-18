/**
 * @file ImportResult.jsx
 * Post-import summary: header with counts, table of imported
 * transactions, and income/expense totals.
 *
 * Fetches transactions by `upload_id` on mount so the user can review
 * exactly what was imported.
 */

import { useState, useEffect } from 'react';
import { getTransactions } from '@/features/transactions/api';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ImportResult');

/**
 * Import success view.
 *
 * @component
 * @param {Object} props
 *
 * @param {Object} props.result
 *        Response from `/tabular/import`. Expected shape:
 *        `{ upload_id, file_name, rows_imported, warnings, … }`.
 * @param {() => void} props.onUploadAnother
 *        Callback to reset the page for a new file.
 * @param {boolean} [props.showHeader=true]
 *        Show the success banner and "Upload Another" button.
 *
 * @returns {JSX.Element|null}
 */
export default function ImportResult({ result, onUploadAnother, showHeader = true }) {
  /** Fetched transactions for this upload. */
  const [transactions, setTransactions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (result?.upload_id) {
      fetchTransactions();
    } else {
      setLoading(false);
    }
  }, [result?.upload_id]);

  /**
   * Load transactions matching this upload.
   */
  const fetchTransactions = async () => {
    try {
      setLoading(true);
      const data = await getTransactions({
        upload_id: result.upload_id,
        limit: 500,
      });
      setTransactions(data.transactions || data);
    } catch (err) {
      setError('Failed to load transactions');
      logger.error('Error fetching transactions:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Format ISO date as `DD-MM-YYYY`.
   * @param {?string} dateString
   */
  const formatDate = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    return `${day}-${month}-${year}`;
  };

  if (!result) return null;

  // ── Summary stats ─────────────────────────────────────────────────

  const totalIncome = transactions
    ? transactions.filter((t) => t.amount > 0).reduce((sum, t) => sum + parseFloat(t.amount), 0)
    : 0;

  const totalExpenses = transactions
    ? Math.abs(
        transactions.filter((t) => t.amount < 0).reduce((sum, t) => sum + parseFloat(t.amount), 0)
      )
    : 0;

  const categorizedCount = transactions ? transactions.filter((t) => t.party_id).length : 0;

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {showHeader && (
        <div className="shrink-0 flex justify-between items-start mb-[16px] gap-[20px]">
          <div className="flex-1 p-[16px_20px] bg-[#d4edda] border border-[#c3e6cb] rounded-[4px]">
            <h2 className="m-[0_0_8px_0] text-[18px] font-semibold text-[#155724]">✓ Import Successful!</h2>
            <div className="flex items-center gap-[12px] text-[13px] flex-wrap">
              <span className="flex items-center gap-[6px]">
                <span className="text-[#155724] font-medium">File:</span>
                <span className="text-[#155724]">{result.file_name}</span>
              </span>
              <span className="text-[#a3cfbb]">|</span>
              <span className="flex items-center gap-[6px]">
                <span className="text-[#155724] font-medium">Rows:</span>
                <span className="text-[#155724]">{result.rows_imported}</span>
              </span>
              <span className="text-[#a3cfbb]">|</span>
              <span className="flex items-center gap-[6px]">
                <span className="text-[#155724] font-medium">Upload ID:</span>
                <span className="text-[#155724]">{result.upload_id}</span>
              </span>
            </div>
          </div>

          <button
            className="shrink-0 p-[10px_20px] bg-[#2196f3] text-white border-none rounded-[4px] text-[14px] font-medium cursor-pointer transition-colors duration-200 hover:bg-[#1976d2]"
            onClick={onUploadAnother}
          >
            Upload Another File
          </button>
        </div>
      )}

      {loading && <div className="text-center p-[40px] text-[#1976d2] text-[16px]">Loading transactions...</div>}

      {error && <div className="p-[12px_16px] bg-[#f8d7da] border border-[#f5c6cb] rounded-[4px] text-[#721c24] mb-[16px]">{error}</div>}

      {transactions && !loading && (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          <div className="shrink-0 flex justify-between items-center mb-[12px]">
            <h3 className="m-0 text-[16px] font-semibold text-text-dark">Imported Transactions</h3>
            <span className="text-[13px] text-text-muted">{transactions.length} transactions</span>
          </div>

          <div className="flex-1 min-h-0 overflow-auto border border-[#dee2e6] rounded-[4px] bg-white">
            <table className="w-full border-collapse text-[13px] font-[-apple-system,BlinkMacSystemFont,'Segoe_UI',Roboto,sans-serif]">
              <thead>
                <tr>
                  <th className="sticky top-0 bg-[#f8f9fa] border-b-2 border-[#dee2e6] p-[10px_12px] text-left font-semibold text-[#495057] whitespace-nowrap z-[1]">Date</th>
                  <th className="sticky top-0 bg-[#f8f9fa] border-b-2 border-[#dee2e6] p-[10px_12px] text-left font-semibold text-[#495057] whitespace-nowrap z-[1]">Description</th>
                  <th className="sticky top-0 bg-[#f8f9fa] border-b-2 border-[#dee2e6] p-[10px_12px] text-right font-semibold text-[#495057] whitespace-nowrap z-[1]">Amount</th>
                  <th className="sticky top-0 bg-[#f8f9fa] border-b-2 border-[#dee2e6] p-[10px_12px] text-left font-semibold text-[#495057] whitespace-nowrap z-[1]">Party</th>
                  <th className="sticky top-0 bg-[#f8f9fa] border-b-2 border-[#dee2e6] p-[10px_12px] text-left font-semibold text-[#495057] whitespace-nowrap z-[1]">Category</th>
                  <th className="sticky top-0 bg-[#f8f9fa] border-b-2 border-[#dee2e6] p-[10px_12px] text-left font-semibold text-[#495057] whitespace-nowrap z-[1]">Type</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="even:bg-[#f8f9fa] hover:bg-[#e9ecef]">
                    <td className="p-[8px_12px] border-b border-[#e9ecef] align-middle w-[90px] whitespace-nowrap">{formatDate(txn.transaction_date)}</td>
                    <td className="p-[8px_12px] border-b border-[#e9ecef] align-middle max-w-[250px] overflow-hidden text-ellipsis whitespace-nowrap" title={txn.description}>
                      {txn.description}
                    </td>
                    <td className={`p-[8px_12px] border-b border-[#e9ecef] align-middle w-[100px] text-right whitespace-nowrap font-semibold ${txn.amount > 0 ? 'text-success' : 'text-danger-alt'}`}>
                      €{Math.abs(parseFloat(txn.amount)).toFixed(2)}
                      <span className="ml-[4px] text-[11px]">{txn.amount > 0 ? '↑' : '↓'}</span>
                    </td>
                    <td className="p-[8px_12px] border-b border-[#e9ecef] align-middle max-w-[120px] overflow-hidden text-ellipsis whitespace-nowrap">{txn.party_name || '-'}</td>
                    <td className="p-[8px_12px] border-b border-[#e9ecef] align-middle max-w-[180px] overflow-hidden text-ellipsis whitespace-nowrap">
                      {txn.category_name ? (
                        <>
                          {txn.category_name}
                          {txn.sub_category_name && (
                            <span className="text-[11px] text-text-muted"> → {txn.sub_category_name}</span>
                          )}
                        </>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="p-[8px_12px] border-b border-[#e9ecef] align-middle max-w-[120px] overflow-hidden text-ellipsis whitespace-nowrap">{txn.type_name || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Summary stats */}
          <div className="shrink-0 mt-[16px] p-[16px_20px] bg-[#f8f9fa] rounded-[4px] border border-[#e9ecef]">
            <h4 className="m-[0_0_12px_0] text-[14px] font-semibold text-text-dark">Summary</h4>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-[20px]">
              <div className="flex flex-col gap-[4px]">
                <span className="text-[12px] text-text-muted font-medium">Total Income</span>
                <span className="text-[18px] font-bold text-success">€{totalIncome.toFixed(2)}</span>
              </div>
              <div className="flex flex-col gap-[4px]">
                <span className="text-[12px] text-text-muted font-medium">Total Expenses</span>
                <span className="text-[18px] font-bold text-danger-alt">€{totalExpenses.toFixed(2)}</span>
              </div>
              <div className="flex flex-col gap-[4px]">
                <span className="text-[12px] text-text-muted font-medium">Categorized</span>
                <span className="text-[18px] font-bold text-text-dark">
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
