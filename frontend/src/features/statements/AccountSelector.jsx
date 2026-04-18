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
      <div className="mt-[20px] p-[20px] border border-border rounded-[4px] bg-surface-alt">
        <h3 className="mt-0">Create New Account</h3>

        <form onSubmit={handleCreateAccount}>
          {fieldErrors._general && (
            <div className="text-[#dc2626] mb-[15px]" role="alert">
              {fieldErrors._general}
            </div>
          )}

          {/* Account Name */}
          <div className="mb-[15px]">
            <label htmlFor="accountName" className="block mb-[5px]">
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
              className={`p-[8px] w-full max-w-[400px] border rounded-[4px] ${
                fieldErrors.accountName
                  ? 'border-[#dc2626] bg-[#fef2f2]'
                  : 'border-[#ccc] bg-white'
              }`}
            />
            {fieldErrors.accountName && (
              <span
                id="accountName-error"
                className="block mt-[4px] text-[#dc2626] text-[14px]"
                role="alert"
              >
                {fieldErrors.accountName}
              </span>
            )}
          </div>

          {/* Account Type */}
          <div className="mb-[15px]">
            <label htmlFor="accountType" className="block mb-[5px]">
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
              className={`p-[8px] w-full max-w-[400px] border rounded-[4px] ${
                fieldErrors.accountType ? 'border-[#dc2626]' : 'border-[#ccc]'
              }`}
            >
              <option value="bank">Bank Account</option>
              <option value="credit">Credit Card</option>
              <option value="cash">Cash</option>
              <option value="investment">Investment</option>
              <option value="other">Other</option>
            </select>
            {fieldErrors.accountType && (
              <span
                className="block mt-[4px] text-[#dc2626] text-[14px]"
                role="alert"
              >
                {fieldErrors.accountType}
              </span>
            )}
          </div>

          {/* Statement Format */}
          <div className="mb-[15px]">
            <label htmlFor="statementFormat" className="block mb-[5px]">
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
              className={`p-[8px] w-full max-w-[400px] border rounded-[4px] ${
                fieldErrors.statementFormat ? 'border-[#dc2626]' : 'border-[#ccc]'
              }`}
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
                className="block mt-[4px] text-[#dc2626] text-[14px]"
                role="alert"
              >
                {fieldErrors.statementFormat}
              </span>
            )}
            <small className="block mt-[4px] text-text-muted">
              Required for importing bank statements. Can be set later.
            </small>
          </div>

          <div className="flex gap-[10px]">
            <button
              type="submit"
              disabled={creating}
              className={`p-[8px_20px] bg-success text-white border-none rounded-[4px] ${
                creating ? 'cursor-not-allowed opacity-60' : 'cursor-pointer opacity-100'
              }`}
            >
              {creating ? 'Creating...' : 'Create Account'}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={creating}
              className="p-[8px_20px] bg-[#6c757d] text-white border-none rounded-[4px] cursor-pointer"
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
      className={`p-[10px] text-[14px] border border-[#ccc] rounded-[4px] w-full h-[42px] ${
        disabled ? 'cursor-not-allowed bg-[#f5f5f5]' : 'cursor-pointer bg-white'
      }`}
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
