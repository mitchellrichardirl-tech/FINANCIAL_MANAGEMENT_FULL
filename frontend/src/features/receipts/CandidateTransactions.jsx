/**
 * @file CandidateTransactions.jsx
 * Compact table of transactions likely to match the currently selected
 * receipt, with a per-row "Select" button to link them.
 *
 * Purely presentational — the parent supplies `transactions` (already
 * fetched) and handles persistence via `onSelectTransaction`.
 */

/**
 * Candidate transaction list for the receipt-linking panel.
 *
 * Rows show date, description, party, and amount. The row for
 * `linkedTransactionId` is highlighted and shows "✓ Linked" instead of
 * the button; all other buttons are disabled once a link exists.
 *
 * @component
 * @param {Object} props
 * @param {Array<Object>} props.transactions
 *        Candidate transactions. Each should have `id`,
 *        `transaction_date`, `description`, `party_name`, `amount`.
 * @param {(tx: Object) => void} props.onSelectTransaction
 *        Called with the chosen transaction when "Select" is clicked.
 * @param {?number} [props.linkedTransactionId]
 *        Id of the transaction already linked (if any). When set, the
 *        matching row shows "✓ Linked" and all other buttons disable.
 * @param {boolean} [props.disabled]
 *        Disable all "Select" buttons (e.g. while a save is in flight).
 * @returns {JSX.Element}
 */
function CandidateTransactions({ transactions, onSelectTransaction, linkedTransactionId, disabled }) {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <div className="mb-3 flex shrink-0 items-center justify-between">
          <h2 className="m-0 text-[1.1rem] font-semibold text-text-dark">Candidate Transactions</h2>
          <span className="text-sm text-text-muted">0 transactions</span>
        </div>
        <div className="p-5 text-center italic text-text-muted">No candidate transactions available.</div>
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
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="mb-3 flex shrink-0 items-center justify-between">
        <h2 className="m-0 text-[1.1rem] font-semibold text-text-dark">Candidate Transactions</h2>
        <span className="text-sm text-text-muted">
          {transactions.length} transaction{transactions.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:rounded [&::-webkit-scrollbar-track]:bg-[#f1f1f1] [&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-[#c1c1c1] [&::-webkit-scrollbar-thumb:hover]:bg-[#a1a1a1]">
        <table className="w-full border-collapse bg-white">
          <thead className="sticky top-0 z-[1] bg-[#f8f9fa]">
            <tr>
              <th className="border-b-2 border-[#dee2e6] p-3 text-left text-sm font-semibold text-[#495057]">Date</th>
              <th className="border-b-2 border-[#dee2e6] p-3 text-left text-sm font-semibold text-[#495057]">Description</th>
              <th className="border-b-2 border-[#dee2e6] p-3 text-left text-sm font-semibold text-[#495057]">Party</th>
              <th className="border-b-2 border-[#dee2e6] p-3 text-right text-sm font-semibold text-[#495057]">Amount</th>
              <th className="border-b-2 border-[#dee2e6] p-3 text-center text-sm font-semibold text-[#495057]">Select</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => {
              const isLinked = linkedTransactionId === tx.id;

              return (
                <tr
                  key={tx.id}
                  className={`animate-[fadeIn_0.3s_ease-in] border-b border-[#dee2e6] transition-colors ${
                    isLinked
                      ? 'animate-[highlightPulse_1s_ease-in-out] bg-[#d4edda] hover:bg-[#c3e6cb]'
                      : 'hover:bg-[#f8f9fa]'
                  }`}
                >
                  <td className="min-w-[100px] whitespace-nowrap overflow-hidden text-ellipsis p-[10px_12px] text-left text-sm font-medium text-[#212529]">
                    <span className="block py-1">{formatDate(tx.transaction_date)}</span>
                  </td>
                  <td className="max-w-[300px] overflow-hidden text-ellipsis p-[10px_12px] text-left text-sm leading-[1.4] text-[#212529]">
                    <span className="block py-1">{tx.description}</span>
                  </td>
                  <td className="min-w-[120px] overflow-hidden text-ellipsis whitespace-nowrap p-[10px_12px] text-left text-sm font-medium text-[#212529]">
                    <span className="block py-1">{tx.party_name || 'Unknown'}</span>
                  </td>
                  <td className="min-w-[80px] overflow-hidden text-ellipsis whitespace-nowrap p-[10px_12px] text-right text-sm text-[#212529]">
                    <span className="block py-1">{formatAmount(tx.amount)}</span>
                  </td>
                  <td className="overflow-hidden text-ellipsis whitespace-nowrap p-[10px_12px] text-center text-sm text-[#212529]">
                    {isLinked ? (
                      <span className="inline-flex items-center gap-1 rounded bg-success px-3 py-1.5 text-sm font-medium text-white">
                        ✓ Linked
                      </span>
                    ) : (
                      <button
                        className="cursor-pointer rounded border-none bg-[#2196f3] px-3 py-1.5 text-sm text-white transition-[background-color,opacity] hover:bg-[#1976d2] active:translate-y-px disabled:cursor-not-allowed disabled:bg-[#6c757d] disabled:opacity-50 disabled:hover:bg-[#6c757d]"
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
