import { apiCall, unwrap } from '@/lib/apiClient';

/**
 * Get all accounts
 */
export async function getAccounts() {
  const response = await apiCall('/accounts');
  // Keep backward compatibility - extract data array if it exists
  return unwrap(response);
}

/**
 * Create a new account
 */
export async function createAccount(accountName, accountType, statementFormat = null) {
  const body = {
    account_name: accountName,
    account_type: accountType
  };
  if (statementFormat) {
    body.statement_format = statementFormat;
  }
  const response = await apiCall('/accounts', {
    method: 'POST',
    body
  });
  return unwrap(response, 'account') || response; // Return the created account
}

export async function previewFile(file, numRows = 20) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('num_rows', numRows);
  formData.append('include_types', 'true');
  return apiCall('/tabular/preview', { method: 'POST', body: formData });
}

export async function importFile(file, startRow, accountId) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('start_row', startRow.toString());
  formData.append('account_id', parseInt(accountId).toString());
  formData.append('has_header', 'true');
  formData.append('skip_empty_rows', 'true');
  formData.append('strip_whitespace', 'true');
  formData.append('original_filename', file.name);
  return apiCall('/tabular/import', { method: 'POST', body: formData });
}

export async function getUploads() {
  return apiCall('/uploads');
}

export async function fetchStatementFormats() {
  const response = await apiCall('/accounts/statement-formats');
  return unwrap(response);  // no key — just strips the .data envelope
}