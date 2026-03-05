import { useState } from 'react';
import { createAccount } from './api';

function AccountSelector({
  accounts,
  selectedAccountId,
  onAccountChange,
  onAccountCreated,
  disabled,
  statementFormats = [],  // <-- new prop
}) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newAccountName, setNewAccountName] = useState('');
  const [newAccountType, setNewAccountType] = useState('bank');
  const [newStatementFormat, setNewStatementFormat] = useState('');  // <-- new
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    const value = e.target.value;
    if (value === 'CREATE_NEW') {
      setShowCreateForm(true);
    } else if (value === '') {
      onAccountChange('');
    } else {
      onAccountChange(parseInt(value, 10));
    }
  };

  const handleCreateAccount = async (e) => {
    e.preventDefault();
    setError('');

    if (!newAccountName.trim()) {
      setError('Account name is required');
      return;
    }

    setCreating(true);
    try {
      const newAccount = await createAccount(
        newAccountName,
        newAccountType,
        newStatementFormat || null,  // <-- send null if not selected
      );

      onAccountCreated(newAccount);
      onAccountChange(newAccount.id);

      // Reset form
      setShowCreateForm(false);
      setNewAccountName('');
      setNewAccountType('bank');
      setNewStatementFormat('');
    } catch (err) {
      setError(err.message || 'Failed to create account');
    } finally {
      setCreating(false);
    }
  };

  const getFormatName = (formatKey) => {
    if (!formatKey) return null;
    const format = statementFormats.find((f) => f.key === formatKey);
    return format ? format.name : formatKey;
  };

  if (showCreateForm) {
    return (
      <div style={{
        marginTop: '20px',
        padding: '20px',
        border: '1px solid #ddd',
        borderRadius: '4px',
        backgroundColor: '#f9f9f9'
      }}>
        <h3 style={{ marginTop: 0 }}>Create New Account</h3>

        <form onSubmit={handleCreateAccount}>
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>
              Account Name:
            </label>
            <input
              type="text"
              value={newAccountName}
              onChange={(e) => setNewAccountName(e.target.value)}
              placeholder="e.g., My Checking Account"
              disabled={creating}
              style={{
                padding: '8px',
                width: '100%',
                maxWidth: '400px',
                border: '1px solid #ccc',
                borderRadius: '4px'
              }}
            />
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>
              Account Type:
            </label>
            <select
              value={newAccountType}
              onChange={(e) => setNewAccountType(e.target.value)}
              disabled={creating}
              style={{
                padding: '8px',
                width: '100%',
                maxWidth: '400px',
                border: '1px solid #ccc',
                borderRadius: '4px'
              }}
            >
              <option value="bank">Bank Account</option>
              <option value="credit">Credit Card</option>
              <option value="cash">Cash</option>
              <option value="investment">Investment</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px' }}>
              Statement Format:
            </label>
            <select
              value={newStatementFormat}
              onChange={(e) => setNewStatementFormat(e.target.value)}
              disabled={creating}
              style={{
                padding: '8px',
                width: '100%',
                maxWidth: '400px',
                border: '1px solid #ccc',
                borderRadius: '4px'
              }}
            >
              <option value="">-- None (configure later) --</option>
              {statementFormats.map((format) => (
                <option key={format.key} value={format.key}>
                  {format.name}
                </option>
              ))}
            </select>
            <small style={{ display: 'block', marginTop: '4px', color: '#666' }}>
              Required for importing bank statements. Can be set later.
            </small>
          </div>

          {error && (
            <div style={{ color: 'red', marginBottom: '15px' }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              type="submit"
              disabled={creating}
              style={{
                padding: '8px 20px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: creating ? 'not-allowed' : 'pointer',
                opacity: creating ? 0.6 : 1
              }}
            >
              {creating ? 'Creating...' : 'Create Account'}
            </button>
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              disabled={creating}
              style={{
                padding: '8px 20px',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <select
      id="account"
      value={selectedAccountId}
      onChange={handleChange}
      disabled={disabled}
      style={{
        padding: '10px',
        fontSize: '14px',
        border: '1px solid #ccc',
        borderRadius: '4px',
        width: '100%',
        height: '42px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        backgroundColor: disabled ? '#f5f5f5' : 'white'
      }}
    >
      <option value="">-- Select an account to import into --</option>
      <option value="CREATE_NEW">➕ Create new account...</option>
      <optgroup label="Existing Accounts">
        {accounts.map((account) => {
          const formatLabel = getFormatName(account.statement_format);
          const displayLabel = formatLabel
            ? `${account.account_name} (${account.account_type}) — ${formatLabel}`
            : `${account.account_name} (${account.account_type}) — ⚠️ No format`;

          return (
            <option key={account.id} value={account.id}>
              {displayLabel}
            </option>
          );
        })}
      </optgroup>
    </select>
  );
}

export default AccountSelector;