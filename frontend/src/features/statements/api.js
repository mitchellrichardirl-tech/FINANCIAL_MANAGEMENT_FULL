/**
 * @file features/statements/api.js
 * HTTP wrappers for the bank-statement import flow.
 *
 * Supports: listing/creating accounts, previewing a tabular file so the
 * user can pick the header row, and submitting the file for import into
 * a chosen account.
 */

import { apiCall, unwrap } from '@/lib/apiClient';
import { AppError } from '@/lib/errors';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('statements:api');

/**
 * Fetch all accounts.
 *
 * @async
 * @returns {Promise<Array<Object>>} Array of account records (envelope stripped).
 * @throws {AppError|ApiError}
 */
export async function getAccounts() {
  const response = await apiCall('/accounts');
  // Keep backward compatibility - extract data array if it exists
  return unwrap(response);
}

/**
 * Create a new account.
 *
 * @async
 * @param {string} accountName - Display name, e.g. `"Amex Gold"`.
 * @param {string} accountType - Backend account-type enum value.
 * @param {?string} [statementFormat=null]
 *        Optional statement-format key (see {@link fetchStatementFormats})
 *        used to auto-map columns on import.
 * @returns {Promise<Object>} The created account record.
 * @throws {AppError|ApiError}
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

/**
 * Ask the backend to parse the first `numRows` of a tabular file
 * (CSV/XLSX/TSV/…) without importing it.
 *
 * Used by the import UI to render a preview grid so the user can
 * identify the header row and sanity-check column detection before
 * committing via {@link importFile}.
 *
 * @async
 * @param {File} file - Statement file selected by the user.
 * @param {number} [numRows=20] - Number of leading rows to return.
 * @returns {Promise<Object>}
 *          Raw API response — typically `{ rows, inferred_types, ... }`.
 * @throws {AppError|ApiError}
 */
export async function previewFile(file, numRows = 20) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('num_rows', numRows);
  formData.append('include_types', 'true');
  const response = await apiCall('/tabular/preview', { method: 'POST', body: formData });
  return unwrap(response);
}

/**
 * Import a statement file into an account.
 *
 * Sends the file plus parsing hints (`start_row`, `has_header`, etc.) to
 * `/tabular/import`. Any synchronous error while assembling the request
 * is normalized into an {@link AppError} tagged with
 * `context: 'importing statement'` so the caller can toast a consistent
 * message.
 *
 * @async
 * @param {File} file - Statement file to import.
 * @param {number} startRow - Zero/one-based row index where data begins
 *        (as chosen in the preview step; passed through verbatim).
 * @param {number|string} accountId - Target account id.
 * @returns {Promise<Object>} Raw API response (import summary / results).
 * @throws {AppError|ApiError}
 */
export async function importFile(file, startRow, accountId) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('start_row', startRow.toString());
    formData.append('account_id', parseInt(accountId).toString());
    formData.append('has_header', 'true');
    formData.append('skip_empty_rows', 'true');
    formData.append('strip_whitespace', 'true');
    formData.append('original_filename', file.name);

    logger.debug('Importing file with parameters:', {
      fileName: file.name,
      fileSize: file.size,
      startRow,
      accountId,
    });
    return apiCall('/tabular/import', { method: 'POST', body: formData });
  } catch (err) {
    throw err instanceof AppError
      ? Object.assign(err, { context: 'importing statement' })
      : new AppError({
          message: err.message,
          userMessage: 'Failed to import the statement.',
          context: 'importing statement',
          cause: err,
        });
  }
}

/**
 * List prior upload batches, newest first.
 *
 * @async
 * @returns {Promise<Object>} Raw API response containing the upload history.
 * @throws {AppError|ApiError}
 */
export async function getUploads() {
  return apiCall('/uploads');
}

/**
 * Fetch the list of statement-format presets the backend knows how to
 * parse (e.g. `"chase_credit_csv"`, `"amex_xlsx"`), for populating the
 * format picker when creating an account.
 *
 * @async
 * @returns {Promise<Array<Object>>} Format descriptors (envelope stripped).
 * @throws {AppError|ApiError}
 */
export async function fetchStatementFormats() {
  const response = await apiCall('/accounts/statement-formats');
  return unwrap(response); // no key — just strips the .data envelope
}