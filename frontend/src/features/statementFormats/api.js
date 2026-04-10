/**
 * @file features/statementFormats/api.js
 * HTTP wrappers for the statement-format management flow.
 *
 * Covers listing all formats (built-in + user), fetching/creating/
 * updating/deleting user formats, and running a draft config against
 * sample rows without persisting anything.
 */

import { apiCall, unwrap } from '@/lib/apiClient';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('statementFormats:api');

// ─────────────────────────────────────────────────────────────────────
// Shape references (JSDoc typedefs — keep in sync with the backend)
// ─────────────────────────────────────────────────────────────────────

/**
 * Summary metadata for one format, as returned by the list endpoint.
 *
 * @typedef {Object} FormatSummary
 * @property {string}  identifier            - Tagged id, e.g. "builtin:ptsb_current" | "user:42".
 * @property {'builtin'|'user'} source
 * @property {boolean} editable
 * @property {string}  bank_name
 * @property {string}  account_type
 * @property {string}  display_name
 * @property {boolean} has_custom_processor  - Built-in only; user formats are always false.
 */

/**
 * Full format record with the complete config, as returned by get-single.
 *
 * @typedef {Object} FormatDetail
 * @property {string}  identifier
 * @property {'builtin'|'user'} source
 * @property {boolean} editable
 * @property {boolean} has_custom_processor
 * @property {Object}  config                - Shape matches `StatementConfig.to_dict()`.
 */

/**
 * Result of a preview call — parsed transactions + any warnings.
 *
 * @typedef {Object} PreviewResult
 * @property {number}   total_parsed
 * @property {Object[]} preview_rows  - Capped server-side (~50).
 * @property {Object[]} warnings      - `ProcessingWarning.to_dict()` shapes.
 */

/**
 * Schema metadata for rendering the form dynamically.
 *
 * @typedef {Object} FormatSchema
 * @property {Array<{name: string, type: string}>} allowed_defaults
 */

// ─────────────────────────────────────────────────────────────────────
// Read
// ─────────────────────────────────────────────────────────────────────

/**
 * List every known statement format.
 *
 * @async
 * @returns {Promise<FormatSummary[]>}
 * @throws {AppError|ApiError}
 */
export async function fetchFormats() {
  const response = await apiCall('/statement-formats');
  return unwrap(response, 'formats') || [];
}

/**
 * Fetch a single format's full config by tagged identifier.
 *
 * @async
 * @param {string} identifier - e.g. "user:42" or "builtin:ptsb_current".
 * @returns {Promise<FormatDetail>}
 * @throws {AppError|ApiError}
 */
export async function fetchFormat(identifier) {
  // Colons are path-safe; no encoding needed for our identifier scheme.
  const response = await apiCall(`/statement-formats/${identifier}`);
  return unwrap(response);
}

/**
 * Fetch schema metadata (e.g. which fields can have config-level defaults).
 * Drives dynamic form rendering so adding a whitelisted default on the
 * backend doesn't require a frontend change.
 *
 * @async
 * @returns {Promise<FormatSchema>}
 * @throws {AppError|ApiError}
 */
export async function fetchFormatSchema() {
  const response = await apiCall('/statement-formats/schema');
  return unwrap(response);
}

// ─────────────────────────────────────────────────────────────────────
// Preview (no persistence)
// ─────────────────────────────────────────────────────────────────────

/**
 * Run a draft config against sample rows and return what the pipeline
 * would produce, without saving anything.
 *
 * @async
 * @param {Object}   config - `StatementConfig.to_dict()` shape.
 * @param {Object[]} rows   - Raw tabular rows as returned by `/tabular/preview`.
 * @returns {Promise<PreviewResult>}
 * @throws {AppError|ApiError}
 *         ApiError with code `INVALID_FORMAT` and `details.missing_columns`
 *         when the config doesn't match the sample — the shape
 *         `ColumnMismatchPanel` consumes directly.
 */
export async function previewFormat(config, rows) {
  logger.debug('Previewing format', {
    display: `${config.bank_name} ${config.account_type}`,
    rows: rows.length,
  });
  const response = await apiCall('/statement-formats/preview', {
    method: 'POST',
    body: { config, rows },
  });
  return unwrap(response);
}

// ─────────────────────────────────────────────────────────────────────
// Write
// ─────────────────────────────────────────────────────────────────────

/**
 * Create a new user-defined statement format.
 *
 * @async
 * @param {Object} config - `StatementConfig.to_dict()` shape.
 * @returns {Promise<Object>} Created row + tagged identifier.
 * @throws {AppError|ApiError}
 *         ApiError 409 when the display name collides with a built-in
 *         or existing user format.
 */
export async function createFormat(config) {
  logger.info('Creating format', {
    display: `${config.bank_name} ${config.account_type}`,
  });
  const response = await apiCall('/statement-formats', {
    method: 'POST',
    body: { config },
  });
  return unwrap(response);
}

/**
 * Replace an existing user-defined format's config.
 *
 * This is a full replacement (PUT, not PATCH) — callers should fetch
 * the current config, edit it, and resubmit the whole thing.
 *
 * @async
 * @param {number} formatId - Numeric DB id (not the tagged identifier).
 * @param {Object} config
 * @returns {Promise<Object>} Updated row.
 * @throws {AppError|ApiError}
 */
export async function updateFormat(formatId, config) {
  logger.info('Updating format', { formatId });
  const response = await apiCall(`/statement-formats/${formatId}`, {
    method: 'PUT',
    body: { config },
  });
  return unwrap(response);
}

/**
 * Delete a user-defined format.
 *
 * @async
 * @param {number} formatId - Numeric DB id.
 * @returns {Promise<{deleted: boolean, id: number}>}
 * @throws {AppError|ApiError}
 *         ApiError 409 when the format is still referenced by one or
 *         more accounts; `details.linked_accounts` lists their ids.
 */
export async function deleteFormat(formatId) {
  logger.info('Deleting format', { formatId });
  const response = await apiCall(`/statement-formats/${formatId}`, {
    method: 'DELETE',
  });
  return unwrap(response);
}