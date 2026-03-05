import './CandidateTransactions.css';

function CandidateTransactions({ 
  transactions, 
  onSelectTransaction, 
  linkedTransactionId,
  disabled 
}) {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="candidate-transactions-container">
        <div className="table-header">
          <h2>Candidate Transactions</h2>
          <span className="transaction-count">0 transactions</span>
        </div>
        <div className="no-transactions">
          No candidate transactions available.
        </div>
      </div>
    );
  }

  const formatDate = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toISOString().split('T')[0];
  };

  const formatAmount = (amount) => {
    if (amount == null) return '';
    return parseFloat(amount).toFixed(2);
  };

  return (
    <div className="candidate-transactions-container">
      <div className="table-header">
        <h2>Candidate Transactions</h2>
        <span className="transaction-count">
          {transactions.length} transaction{transactions.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="table-wrapper">
        <table className="candidate-transactions-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Party</th>
              <th className="amount-header">Amount</th>
              <th className="actions-header">Select</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => {
              const isLinked = linkedTransactionId === tx.id;
              
              return (
                <tr 
                  key={tx.id} 
                  className={`transaction-row ${isLinked ? 'linked' : ''}`}
                >
                  <td className="date-cell">
                    <span className="view-value">{formatDate(tx.transaction_date)}</span>
                  </td>
                  <td className="description-cell">
                    <span className="view-value">{tx.description}</span>
                  </td>
                  <td className="party-cell">
                    <span className="view-value">{tx.party_name || 'Unknown'}</span>
                  </td>
                  <td className="amount-cell">
                    <span className="view-value">{formatAmount(tx.amount)}</span>
                  </td>
                  <td className="actions-cell">
                    {isLinked ? (
                      <span className="linked-indicator">
                        ✓ Linked
                      </span>
                    ) : (
                      <button 
                        className="btn-select"
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