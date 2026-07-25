/**
 * @file CandidateTransactions.jsx
 * Compact table of transactions likely to match the currently selected
 * receipt, with a per-row "Select" button to link them.
 *
 * Purely presentational — the parent supplies `transactions` (already
 * fetched) and handles persistence via `onSelectTransaction`.
 */
/* ── Reused class strings ──────────────────────────────────────────── */
/** Cell bases omit text-align — each cell sets its own. */
const TH =
  'border-b-2 border-gray-300 p-2 text-[13px] font-semibold text-gray-600 md:p-3 md:text-sm';
const TD = 'p-2 text-[13px] text-gray-800 md:px-3 md:py-2.5 md:text-sm';
/** `.view-value` */
const VIEW = 'block py-1';
const BTN_SELECT =
  'cursor-pointer rounded border-none bg-[#2196f3] px-2 py-1 text-xs text-white ' +
  'transition-[background-color,opacity] hover:bg-[#1976d2] active:translate-y-px ' +
  'disabled:cursor-not-allowed disabled:bg-[#6c757d] disabled:opacity-50 ' +
  'disabled:hover:bg-[#6c757d] md:px-3 md:py-1.5 md:text-sm';
const SCROLLBAR = [
  '[&::-webkit-scrollbar]:w-2',
  '[&::-webkit-scrollbar-track]:rounded [&::-webkit-scrollbar-track]:bg-gray-100',
  '[&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-[#c1c1c1]',
  '[&::-webkit-scrollbar-thumb:hover]:bg-[#a1a1a1]',
].join(' ');
/**
 * Panel header — extracted because both the empty and populated
 * branches render it identically.
 */
function PanelHeader({ count }) {
  return (
    <div className="mb-3 flex shrink-0 items-center justify-between">
      <h2 className="text-[1.1rem] font-semibold text-gray-800">Candidate Transactions</h2>
      <span className="text-sm text-muted">
        {count} transaction{count !== 1 ? 's' : ''}
      </span>
    </div>
  );
}
/**
 * Candidate transaction list for the receipt-linking panel.
 *
 * @component
 * @param {Object} props
 * @param {Array<Object>} props.transactions
 * @param {(tx: Object) => void} props.onSelectTransaction
 * @param {?number} [props.linkedTransactionId]
 * @param {boolean} [props.disabled]
 * @returns {JSX.Element}
 */
function CandidateTransactions({
  transactions,
  onSelectTransaction,
  linkedTransactionId,
  disabled,
}) {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <PanelHeader count={0} />
        <div className="p-5 text-center italic text-muted">
          No candidate transactions available.
        </div>
      </div>
    );
  }
  /** Format an ISO date as `YYYY-MM-DD`. */
  const formatDate = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toISOString().split('T')[0];
  };
  /** Format an amount to two decimals. */
  const formatAmount = (amount) => {
    if (amount == null) return '';
    return parseFloat(amount).toFixed(2);
  };
  return (
    /* min-h-0 is what lets the table-wrapper actually scroll */
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <PanelHeader count={transactions.length} />
      <div className={`min-h-0 flex-1 overflow-y-auto ${SCROLLBAR}`}>
        <table className="w-full bg-white">
          <thead className="sticky top-0 z-[1] bg-gray-50">
            <tr>
              <th className={`${TH} text-left`}>Date</th>
              <th className={`${TH} text-left`}>Description</th>
              <th className={`${TH} text-left`}>Party</th>
              <th className={`${TH} text-right`}>Amount</th>
              <th className={`${TH} text-center`}>Select</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => {
              const isLinked = linkedTransactionId === tx.id;
              return (
                <tr
                  key={tx.id}
                  className={
                    isLinked
                      ? 'animate-highlight-pulse border-b border-gray-300 bg-[#d4edda] transition-colors duration-200 hover:bg-[#c3e6cb]'
                      : 'animate-fade-in border-b border-gray-300 transition-colors duration-200 hover:bg-gray-50'
                  }
                >
                  <td className={`${TD} min-w-[100px] truncate text-left font-medium`}>
                    <span className={VIEW}>{formatDate(tx.transaction_date)}</span>
                  </td>
                  {/* Description wraps instead of truncating */}
                  <td className={`${TD} max-w-[150px] text-left leading-[1.4] md:max-w-[300px]`}>
                    <span className={VIEW}>{tx.description}</span>
                  </td>
                  <td className={`${TD} min-w-[120px] truncate text-left font-medium`}>
                    <span className={VIEW}>{tx.party_name || 'Unknown'}</span>
                  </td>
                  <td className={`${TD} min-w-[80px] truncate text-right`}>
                    <span className={VIEW}>{formatAmount(tx.amount)}</span>
                  </td>
                  <td className={`${TD} truncate text-center`}>
                    {isLinked ? (
                      <span className="inline-flex items-center gap-1 rounded bg-[#28a745] px-3 py-1.5 text-sm font-medium text-white">
                        ✓ Linked
                      </span>
                    ) : (
                      <button
                        className={BTN_SELECT}
                        onClick={() => onSelectTransaction && onSelectTransaction(tx)}
                        title="Select this transaction"
                        disabled={disabled || linkedTransactionId !== null}
                      >
                        Select
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
export default CandidateTransactions;