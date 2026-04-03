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
import './ImportResult.css';
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
    <div className="import-result">
      {showHeader && (
        <div className="import-result-header">
          <div className="import-success-banner">
            <h2>✓ Import Successful!</h2>
            <div className="import-details">
              <span className="import-detail-item">
                <span className="detail-label">File:</span>
                <span className="detail-value">{result.file_name}</span>
              </span>
              <span className="import-detail-divider">|</span>
              <span className="import-detail-item">
                <span className="detail-label">Rows:</span>
                <span className="detail-value">{result.rows_imported}</span>
              </span>
              <span className="import-detail-divider">|</span>
              <span className="import-detail-item">
                <span className="detail-label">Upload ID:</span>
                <span className="detail-value">{result.upload_id}</span>
              </span>
            </div>
          </div>

          <button className="upload-another-btn" onClick={onUploadAnother}>
            Upload Another File
          </button>
        </div>
      )}

      {loading && <div className="import-loading">Loading transactions...</div>}

      {error && <div className="import-error">{error}</div>}

      {transactions && !loading && (
        <div className="import-transactions-section">
          <div className="transactions-header">
            <h3>Imported Transactions</h3>
            <span className="transactions-count">{transactions.length} transactions</span>
          </div>

          <div className="import-table-wrapper">
            <table className="import-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th className="amount-header">Amount</th>
                  <th>Party</th>
                  <th>Category</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id}>
                    <td className="date-cell">{formatDate(txn.transaction_date)}</td>
                    <td className="description-cell" title={txn.description}>
                      {txn.description}
                    </td>
                    <td className={`amount-cell ${txn.amount > 0 ? 'positive' : 'negative'}`}>
                      €{Math.abs(parseFloat(txn.amount)).toFixed(2)}
                      <span className="amount-indicator">{txn.amount > 0 ? '↑' : '↓'}</span>
                    </td>
                    <td className="party-cell">{txn.party_name || '-'}</td>
                    <td className="category-cell">
                      {txn.category_name ? (
                        <>
                          {txn.category_name}
                          {txn.sub_category_name && (
                            <span className="sub-category"> → {txn.sub_category_name}</span>
                          )}
                        </>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="type-cell">{txn.type_name || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Summary stats */}
          <div className="import-summary">
            <h4>Summary</h4>
            <div className="summary-grid">
              <div className="summary-stat">
                <span className="stat-label">Total Income</span>
                <span className="stat-value positive">€{totalIncome.toFixed(2)}</span>
              </div>
              <div className="summary-stat">
                <span className="stat-label">Total Expenses</span>
                <span className="stat-value negative">€{totalExpenses.toFixed(2)}</span>
              </div>
              <div className="summary-stat">
                <span className="stat-label">Categorized</span>
                <span className="stat-value">
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
