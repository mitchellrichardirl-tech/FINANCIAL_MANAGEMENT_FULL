function CandidateTransactions({ transactions, onSelectTransaction, linkedTransactionId, disabled }) {
  const headingCls = 'flex justify-between items-center mb-3 shrink-0';
  const titleCls = 'text-[1.1rem] font-semibold m-0 text-[#333]';
  const countCls = 'text-[#666] text-sm';
  const emptyCls = 'p-5 text-center text-[#666] italic';
  const containerCls = 'flex flex-col h-full min-h-0 overflow-hidden';

  if (!transactions || transactions.length === 0) {
    return (
      <div className={containerCls}>
        <div className={headingCls}>
          <h2 className={titleCls}>Candidate Transactions</h2>
          <span className={countCls}>0 transactions</span>
        </div>
        <div className={emptyCls}>No candidate transactions available.</div>
      </div>
    );
  }

  const formatDate = (s) => (s ? new Date(s).toISOString().split('T')[0] : '');
  const formatAmount = (a) => (a == null ? '' : parseFloat(a).toFixed(2));

  const thCls =
    'sticky top-0 bg-[#f8f9fa] z-[1] py-3 px-3 text-left font-semibold text-[#495057] border-b-2 border-[#dee2e6] text-sm';
  const tdCls = 'py-2.5 px-3 text-[#212529] text-sm border-b border-[#dee2e6]';

  return (
    <div className={containerCls}>
      <div className={headingCls}>
        <h2 className={titleCls}>Candidate Transactions</h2>
        <span className={countCls}>
          {transactions.length} transaction{transactions.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full border-collapse bg-white">
          <thead>
            <tr>
              <th className={thCls}>Date</th>
              <th className={thCls}>Description</th>
              <th className={thCls}>Party</th>
              <th className={`${thCls} !text-right`}>Amount</th>
              <th className={`${thCls} !text-center`}>Select</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => {
              const isLinked = linkedTransactionId === tx.id;
              return (
                <tr
                  key={tx.id}
                  className={`transition-colors duration-200 animate-fade-in ${
                    isLinked
                      ? 'bg-[#d4edda] hover:bg-[#c3e6cb] animate-highlight-pulse'
                      : 'hover:bg-[#f8f9fa]'
                  }`}
                >
                  <td className={`${tdCls} whitespace-nowrap font-medium min-w-[100px]`}>
                    {formatDate(tx.transaction_date)}
                  </td>
                  <td className={`${tdCls} max-w-[300px] whitespace-normal leading-snug`}>
                    {tx.description}
                  </td>
                  <td className={`${tdCls} font-medium min-w-[120px] whitespace-nowrap overflow-hidden text-ellipsis`}>
                    {tx.party_name || 'Unknown'}
                  </td>
                  <td className={`${tdCls} !text-right min-w-[80px]`}>
                    {formatAmount(tx.amount)}
                  </td>
                  <td className={`${tdCls} !text-center`}>
                    {isLinked ? (
                      <span className="inline-flex items-center gap-1 py-1.5 px-3 bg-[#28a745] text-white rounded text-sm font-medium">
                        ✓ Linked
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onSelectTransaction && onSelectTransaction(tx)}
                        title="Select this transaction"
                        disabled={disabled || linkedTransactionId !== null}
                        className="py-1.5 px-3 border-0 rounded cursor-pointer text-sm bg-[#2196f3] text-white hover:enabled:bg-[#1976d2] active:enabled:translate-y-px disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-[#6c757d]"
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
