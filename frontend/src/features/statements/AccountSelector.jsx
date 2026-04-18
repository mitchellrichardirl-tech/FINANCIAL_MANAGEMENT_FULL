import { useForm } from 'react-hook-form';
import { useState } from 'react';
import { useCreateAccount } from './hooks';
import { ErrorCode } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';

const logger = createLogger('AccountSelector');

const FIELD_MAP = {
  account_name: 'accountName',
  account_type: 'accountType',
  statement_format: 'statementFormat',
};

const NAME_FIELD_CODES = new Set([ErrorCode.DUPLICATE_NAME, ErrorCode.REQUIRED_FIELD]);

function AccountSelector({
  accounts,
  selectedAccountId,
  onAccountChange,
  disabled,
  statementFormats = [],
}) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [generalError, setGeneralError] = useState(null);
  const createAccount = useCreateAccount();

  const {
    register,
    handleSubmit,
    reset: resetForm,
    setError,
    clearErrors,
    formState: { errors },
  } = useForm({
    defaultValues: { accountName: '', accountType: 'bank', statementFormat: '' },
  });

  logger.info('Available statement formats:', statementFormats);

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

  const onSubmit = async (data) => {
    setGeneralError(null);
    clearErrors();
    try {
      const newAccount = await createAccount.mutateAsync({
        accountName: data.accountName,
        accountType: data.accountType,
        statementFormat: data.statementFormat || null,
      });
      onAccountChange(newAccount.id);
      setShowCreateForm(false);
      resetForm();
    } catch (err) {
      const message = err.userMessage || err.message || 'Failed to create account';
      const mappedField = err.field ? FIELD_MAP[err.field] : null;
      if (mappedField) {
        setError(mappedField, { type: 'server', message });
      } else if (NAME_FIELD_CODES.has(err.code)) {
        setError('accountName', { type: 'server', message });
      } else {
        setGeneralError(message);
      }
    }
  };

  const handleCancel = () => {
    setShowCreateForm(false);
    setGeneralError(null);
    clearErrors();
    resetForm();
  };

  const getFormatName = (formatKey) => {
    if (!formatKey) return null;
    const format = statementFormats.find((f) => f.identifier === formatKey);
    return format ? format.name : formatKey;
  };

  const creating = createAccount.isPending;
  const errCls = (has) =>
    `p-2 w-full max-w-[400px] border rounded ${has ? 'border-[#dc2626] bg-[#fef2f2]' : 'border-[#ccc] bg-white'}`;

  if (showCreateForm) {
    return (
      <div className="mt-5 p-5 border border-[#ddd] rounded bg-[#f9f9f9]">
        <h3 className="mt-0 text-lg font-semibold">Create New Account</h3>

        <form onSubmit={handleSubmit(onSubmit)}>
          {generalError && (
            <div className="text-[#dc2626] mb-4" role="alert">{generalError}</div>
          )}

          <div className="mb-4">
            <label htmlFor="accountName" className="block mb-1">Account Name:</label>
            <input
              id="accountName"
              type="text"
              {...register('accountName', { required: 'Account name is required' })}
              placeholder="e.g., My Checking Account"
              disabled={creating}
              aria-invalid={!!errors.accountName}
              className={errCls(!!errors.accountName)}
            />
            {errors.accountName && (
              <span className="block mt-1 text-[#dc2626] text-sm" role="alert">
                {errors.accountName.message}
              </span>
            )}
          </div>

          <div className="mb-4">
            <label htmlFor="accountType" className="block mb-1">Account Type:</label>
            <select
              id="accountType"
              {...register('accountType')}
              disabled={creating}
              aria-invalid={!!errors.accountType}
              className={errCls(!!errors.accountType)}
            >
              <option value="bank">Bank Account</option>
              <option value="credit">Credit Card</option>
              <option value="cash">Cash</option>
              <option value="investment">Investment</option>
              <option value="other">Other</option>
            </select>
            {errors.accountType && (
              <span className="block mt-1 text-[#dc2626] text-sm" role="alert">
                {errors.accountType.message}
              </span>
            )}
          </div>

          <div className="mb-4">
            <label htmlFor="statementFormat" className="block mb-1">Statement Format:</label>
            <select
              id="statementFormat"
              {...register('statementFormat')}
              disabled={creating}
              aria-invalid={!!errors.statementFormat}
              className={errCls(!!errors.statementFormat)}
            >
              <option value="">-- None (configure later) --</option>
              {statementFormats.map((format) => (
                <option key={format.identifier} value={format.identifier}>
                  {format.display_name}
                </option>
              ))}
            </select>
            {errors.statementFormat && (
              <span className="block mt-1 text-[#dc2626] text-sm" role="alert">
                {errors.statementFormat.message}
              </span>
            )}
            <small className="block mt-1 text-[#666]">
              Required for importing bank statements. Can be set later.
            </small>
          </div>

          <div className="flex gap-[10px]">
            <button
              type="submit"
              disabled={creating}
              className="py-2 px-5 bg-[#28a745] text-white border-0 rounded cursor-pointer hover:enabled:bg-[#218838] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {creating ? 'Creating...' : 'Create Account'}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={creating}
              className="py-2 px-5 bg-[#6c757d] text-white border-0 rounded cursor-pointer"
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
      className={`p-[10px] text-sm border border-[#ccc] rounded w-full h-[42px] ${disabled ? 'cursor-not-allowed bg-[#f5f5f5]' : 'cursor-pointer bg-white'}`}
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
