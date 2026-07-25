/**
 * @file ImportResult.jsx
 * Post-import summary: header with counts, table of imported
 * transactions, and income/expense totals.
 *
 * Fetches transactions by `upload_id` on mount so the user can review
 * exactly what was imported.
 *
 * Layout contract: renders as a flex-column child and owns an internal
 * scroll region (the transactions table). The parent must be
 * `flex flex-col` with a definite height, otherwise this degrades to
 * auto-height and the page scrolls instead.
 */
import { useState, useEffect } from 'react';
import { getTransactions } from '@/features/transactions/api';
import { createLogger } from '@/lib/logger';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ImportResult');
/* ── Table cell bases (text-align set per-cell to avoid conflicts) ── */
const TH =
  'sticky top-0 z-[1] whitespace-nowrap border-b-2 border-gray-300 bg-gray-50 ' +
  'px-3 py-2.5 font-semibold text-gray-600';
const TD = 'border-b border-gray-200 px-3 py-2 align-middle';
/* ── Reused detail/stat label colors ── */
const DETAIL_TXT = 'text-[#155724]';
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
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {showHeader && (
        <div className="shrink-0 mb-4 flex items-start justify-between gap-5">
          <div className="flex-1 rounded border border-[#c3e6cb] bg-[#d4edda] px-5 py-4">
            <h2 className={`mb-2 text-lg font-semibold ${DETAIL_TXT}`}>
              ✓ Import Successful!
            </h2>
            <div className="flex flex-wrap items-center gap-3 text-[13px]">
              <span className="flex items-center gap-1.5">
                <span className={`font-medium ${DETAIL_TXT}`}>File:</span>
                <span className={DETAIL_TXT}>{result.file_name}</span>
              </span>
              <span className="text-[#a3cfbb]">|</span>
              <span className="flex items-center gap-1.5">
                <span className={`font-medium ${DETAIL_TXT}`}>Rows:</span>
                <span className={DETAIL_TXT}>{result.rows_imported}</span>
              </span>
              <span className="text-[#a3cfbb]">|</span>
              <span className="flex items-center gap-1.5">
                <span className={`font-medium ${DETAIL_TXT}`}>Upload ID:</span>
                <span className={DETAIL_TXT}>{result.upload_id}</span>
              </span>
            </div>
          </div>
          <button
            className="shrink-0 cursor-pointer rounded bg-[#2196f3] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#1976d2]"
            onClick={onUploadAnother}
          >
            Upload Another File
          </button>
        </div>
      )}
      {loading && (
        <div className="shrink-0 p-10 text-center text-base text-[#1976d2]">
          Loading transactions...
        </div>
      )}
      {error && (
        <div className="shrink-0 mb-4 rounded border border-danger-border bg-danger-bg px-4 py-3 text-danger-text">
          {error}
        </div>
      )}
      {transactions && !loading && (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="shrink-0 mb-3 flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-800">
              Imported Transactions
            </h3>
            <span className="text-[13px] text-muted">
              {transactions.length} transactions
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-auto rounded border border-gray-300 bg-white">
            <table className="w-full font-sans text-[13px]">
              <thead>
                <tr>
                  <th className={`${TH} text-left`}>Date</th>
                  <th className={`${TH} text-left`}>Description</th>
                  <th className={`${TH} text-right`}>Amount</th>
                  <th className={`${TH} text-left`}>Party</th>
                  <th className={`${TH} text-left`}>Category</th>
                  <th className={`${TH} text-left`}>Type</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="even:bg-gray-50 hover:bg-gray-200">
                    <td className={`${TD} w-[90px] whitespace-nowrap`}>
                      {formatDate(txn.transaction_date)}
                    </td>
                    <td className={`${TD} max-w-[250px] truncate`} title={txn.description}>
                      {txn.description}
                    </td>
                    <td
                      className={`${TD} w-[100px] whitespace-nowrap text-right font-semibold ${
                        txn.amount > 0 ? 'text-[#28a745]' : 'text-[#dc3545]'
                      }`}
                    >
                      €{Math.abs(parseFloat(txn.amount)).toFixed(2)}
                      <span className="ml-1 text-[11px]">{txn.amount > 0 ? '↑' : '↓'}</span>
                    </td>
                    <td className={`${TD} max-w-[120px] truncate`}>{txn.party_name || '-'}</td>
                    <td className={`${TD} max-w-[180px] truncate`}>
                      {txn.category_name ? (
                        <>
                          {txn.category_name}
                          {txn.sub_category_name && (
                            <span className="text-[11px] text-muted">
                              {' '}
                              → {txn.sub_category_name}
                            </span>
                          )}
                        </>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className={`${TD} max-w-[120px] truncate`}>{txn.type_name || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Summary stats */}
          <div className="shrink-0 mt-4 rounded border border-gray-200 bg-gray-50 px-5 py-4">
            <h4 className="mb-3 text-sm font-semibold text-gray-800">Summary</h4>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-5">
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-muted">Total Income</span>
                <span className="text-lg font-bold text-[#28a745]">
                  €{totalIncome.toFixed(2)}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-muted">Total Expenses</span>
                <span className="text-lg font-bold text-[#dc3545]">
                  €{totalExpenses.toFixed(2)}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-muted">Categorized</span>
                <span className="text-lg font-bold text-gray-800">
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