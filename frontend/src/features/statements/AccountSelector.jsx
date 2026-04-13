/**
 * @file AccountSelector.jsx
 * Dropdown for selecting an existing account or creating a new one
 * inline.
 *
 * When "Create new account…" is selected, the dropdown is replaced by
 * a form. On success, the new account is appended to the list and
 * auto-selected.
 */

import { useState } from 'react';
import { createAccount } from './api';
import { ErrorCode } from '@/lib/apiErrors';

import { createLogger } from '@/lib/logger';

const logger = createLogger('AccountSelector');

/**
 * Maps backend field names to form input ids for error routing.
 * @type {Record<string, string>}
 */
const FIELD_MAP = {
  account_name: 'accountName',
  account_type: 'accountType',
  statement_format: 'statementFormat',
};

/** Error codes that should highlight the name field specifically. */
const NAME_FIELD_CODES = new Set([ErrorCode.DUPLICATE_NAME, ErrorCode.REQUIRED_FIELD]);

/**
 * Account selector with inline create form.
 *
 * @component
 * @param {Object} props
 *
 * @param {Array<Object>} props.accounts
 *        List of existing accounts.
 * @param {number|string} props.selectedAccountId
 *        Currently selected account id (empty string = none).
 * @param {(id: number|string) => void} props.onAccountChange
 *        Called when selection changes.
 * @param {(account: Object) => void} props.onAccountCreated
 *        Called after a new account is created so the parent can
 *        append it to the list.
 * @param {boolean} [props.disabled=false]
 * @param {Array<{key: string, name: string}>} [props.statementFormats=[]]
 *        Available statement format presets.
 *
 * @returns {JSX.Element}
 */
function AccountSelector({
  accounts,
  selectedAccountId,
  onAccountChange,
  onAccountCreated,
  disabled,
  statementFormats = [],
}) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newAccountName, setNewAccountName] = useState('');
  const [newAccountType, setNewAccountType] = useState('bank');
  const [newStatementFormat, setNewStatementFormat] = useState('');
  const [creating, setCreating] = useState(false);
  /**
   * Field-level errors.
   * `_general` holds errors that don't map to a specific field.
   * @type {[Record<string, string>, Function]}
   */
  const [fieldErrors, setFieldErrors] = useState({});

  logger.info('Available statement formats:', statementFormats);

  /**
   * Clear a single field error (called as user types).
   * @param {string} field
   */
  const clearFieldError = (field) => {
    if (fieldErrors[field]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  /**
   * Handle dropdown change. If "CREATE_NEW" is selected, switch to
   * the inline form.
   */
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

  /**
   * Submit the create-account form.
   */
  const handleCreateAccount = async (e) => {
    e.preventDefault();
    setFieldErrors({});

    if (!newAccountName.trim()) {
      setFieldErrors({ accountName: 'Account name is required' });
      return;
    }

    setCreating(true);
    try {
      const newAccount = await createAccount(
        newAccountName,
        newAccountType,
        newStatementFormat || null
      );

      onAccountCreated(newAccount);
      onAccountChange(newAccount.id);

      // Reset form
      setShowCreateForm(false);
      setNewAccountName('');
      setNewAccountType('bank');
      setNewStatementFormat('');
    } catch (err) {
      const message = err.userMessage || err.message || 'Failed to create account';

      const mappedField = err.field ? FIELD_MAP[err.field] : null;

      if (mappedField) {
        setFieldErrors({ [mappedField]: message });
      } else if (NAME_FIELD_CODES.has(err.code)) {
        setFieldErrors({ accountName: message });
      } else {
        setFieldErrors({ _general: message });
      }
    } finally {
      setCreating(false);
    }
  };

  /** Cancel and return to the dropdown. */
  const handleCancel = () => {
    setShowCreateForm(false);
    setFieldErrors({});
    setNewAccountName('');
    setNewAccountType('bank');
    setNewStatementFormat('');
  };

  /**
   * Resolve a format key to its display name.
   * @param {?string} formatKey
   */
  const getFormatName = (formatKey) => {
    if (!formatKey) return null;
    const format = statementFormats.find((f) => f.identifier === formatKey);
    return format ? format.name : formatKey;
  };

  // ── Render: create form ───────────────────────────────────────────

  if (showCreateForm) {
    return (
      <div
        style={{
          marginTop: '20px',
          padding: '20px',
          border: '1px solid #ddd',
          borderRadius: '4px',
          backgroundColor: '#f9f9f9',
        }}
      >
        <h3 style={{ marginTop: 0 }}>Create New Account</h3>

        <form onSubmit={handleCreateAccount}>
          {fieldErrors._general && (
            <div style={{ color: '#dc2626', marginBottom: '15px' }} role="alert">
              {fieldErrors._general}
            </div>
          )}

          {/* Account Name */}
          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="accountName" style={{ display: 'block', marginBottom: '5px' }}>
              Account Name:
            </label>
            <input
              id="accountName"
              type="text"
              value={newAccountName}
              onChange={(e) => {
                setNewAccountName(e.target.value);
                clearFieldError('accountName');
              }}
              placeholder="e.g., My Checking Account"
              disabled={creating}
              aria-invalid={!!fieldErrors.accountName}
              aria-describedby={fieldErrors.accountName ? 'accountName-error' : undefined}
              style={{
                padding: '8px',
                width: '100%',
                maxWidth: '400px',
                border: `1px solid ${fieldErrors.accountName ? '#dc2626' : '#ccc'}`,
                borderRadius: '4px',
                backgroundColor: fieldErrors.accountName ? '#fef2f2' : 'white',
              }}
            />
            {fieldErrors.accountName && (
              <span
                id="accountName-error"
                style={{ display: 'block', marginTop: '4px', color: '#dc2626', fontSize: '14px' }}
                role="alert"
              >
                {fieldErrors.accountName}
              </span>
            )}
          </div>

          {/* Account Type */}
          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="accountType" style={{ display: 'block', marginBottom: '5px' }}>
              Account Type:
            </label>
            <select
              id="accountType"
              value={newAccountType}
              onChange={(e) => {
                setNewAccountType(e.target.value);
                clearFieldError('accountType');
              }}
              disabled={creating}
              aria-invalid={!!fieldErrors.accountType}
              style={{
                padding: '8px',
                width: '100%',
                maxWidth: '400px',
                border: `1px solid ${fieldErrors.accountType ? '#dc2626' : '#ccc'}`,
                borderRadius: '4px',
              }}
            >
              <option value="bank">Bank Account</option>
              <option value="credit">Credit Card</option>
              <option value="cash">Cash</option>
              <option value="investment">Investment</option>
              <option value="other">Other</option>
            </select>
            {fieldErrors.accountType && (
              <span
                style={{ display: 'block', marginTop: '4px', color: '#dc2626', fontSize: '14px' }}
                role="alert"
              >
                {fieldErrors.accountType}
              </span>
            )}
          </div>

          {/* Statement Format */}
          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="statementFormat" style={{ display: 'block', marginBottom: '5px' }}>
              Statement Format:
            </label>
            <select
              id="statementFormat"
              value={newStatementFormat}
              onChange={(e) => {
                setNewStatementFormat(e.target.value);
                clearFieldError('statementFormat');
              }}
              disabled={creating}
              aria-invalid={!!fieldErrors.statementFormat}
              style={{
                padding: '8px',
                width: '100%',
                maxWidth: '400px',
                border: `1px solid ${fieldErrors.statementFormat ? '#dc2626' : '#ccc'}`,
                borderRadius: '4px',
              }}
            >
              <option value="">-- None (configure later) --</option>
              {statementFormats.map((format) => (
                <option key={format.identifier} value={format.identifier}>
                  {format.display_name}
                </option>
              ))}
            </select>
            {fieldErrors.statementFormat && (
              <span
                style={{ display: 'block', marginTop: '4px', color: '#dc2626', fontSize: '14px' }}
                role="alert"
              >
                {fieldErrors.statementFormat}
              </span>
            )}
            <small style={{ display: 'block', marginTop: '4px', color: '#666' }}>
              Required for importing bank statements. Can be set later.
            </small>
          </div>

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
                opacity: creating ? 0.6 : 1,
              }}
            >
              {creating ? 'Creating...' : 'Create Account'}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={creating}
              style={{
                padding: '8px 20px',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    );
  }

  // ── Render: dropdown ──────────────────────────────────────────────

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
        backgroundColor: disabled ? '#f5f5f5' : 'white',
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