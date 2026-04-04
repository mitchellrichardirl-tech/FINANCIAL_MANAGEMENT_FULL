/**
 * @file apiErrors.js
 * Parsing and presentation helpers for backend error responses.
 *
 * The backend returns errors in the shape:
 *   { success: false, error: { code, message, field?, entity?, details? } }
 *
 * This module normalizes whatever we receive (fetch `Response`, Axios error,
 * or a raw object) into a {@link ParsedError}, and maps error codes to
 * user-friendly strings for display in toasts / form validation.
 */

/**
 * A normalized, UI-ready representation of a backend error.
 *
 * @typedef {Object} ParsedError
 * @property {string} code        - Backend error code (one of {@link ErrorCode}).
 * @property {string} message     - Technical message from the server (not for end users).
 * @property {?string} field      - Field name the error is attached to, if any.
 * @property {?string} entity     - Domain entity the error relates to (e.g. `"Category"`).
 * @property {Object} details     - Arbitrary extra data (e.g. `missing_columns`, `value`).
 * @property {number} status      - HTTP status code.
 * @property {*} [raw]            - The original error payload, for debugging.
 * @property {string} [userMessage] - Precomputed user-facing message (optional).
 */

/**
 * Error codes returned by the backend.
 * Keep in sync with `src/api/utils/errors.py → ErrorCode`.
 *
 * @readonly
 * @enum {string}
 */
export const ErrorCode = {
  REQUIRED_FIELD: 'REQUIRED_FIELD',
  INVALID_FORMAT: 'INVALID_FORMAT',
  INVALID_VALUE: 'INVALID_VALUE',
  DUPLICATE_NAME: 'DUPLICATE_NAME',
  FOREIGN_KEY_VIOLATION: 'FOREIGN_KEY_VIOLATION',
  HAS_DEPENDENCIES: 'HAS_DEPENDENCIES',
  NOT_FOUND: 'NOT_FOUND',
  PARENT_NOT_FOUND: 'PARENT_NOT_FOUND',
  DATABASE_ERROR: 'DATABASE_ERROR',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
};

/**
 * User-friendly message templates keyed by {@link ErrorCode}.
 * Each value is a function receiving the {@link ParsedError} so it can
 * interpolate `field`, `entity`, `details`, etc.
 *
 * @type {Object<string, (err: ParsedError) => string>}
 */
const ERROR_MESSAGES = {
  [ErrorCode.REQUIRED_FIELD]: (err) =>
    `${formatField(err.field)} is required.`,

  [ErrorCode.INVALID_FORMAT]: (err) =>
    err.details?.missing_columns
      ? `File doesn't match expected format. Missing: ${err.details.missing_columns.join(', ')}.`
      : err.message,

  [ErrorCode.INVALID_VALUE]: (err) =>
    err.field
      ? `Invalid value for ${formatField(err.field)}.`
      : err.message,

  [ErrorCode.DUPLICATE_NAME]: (err) =>
    err.details?.value
      ? `${err.entity || 'Item'} "${err.details.value}" already exists.`
      : `${err.entity || 'Item'} with this name already exists.`,

  [ErrorCode.NOT_FOUND]: (err) =>
    `${err.entity || 'Item'} not found. It may have been deleted.`,

  [ErrorCode.PARENT_NOT_FOUND]: () =>
    'The selected parent no longer exists. Please refresh and try again.',

  [ErrorCode.HAS_DEPENDENCIES]: (err) =>
    `Cannot delete: has linked ${err.details?.dependency || 'records'}.`,

  [ErrorCode.FOREIGN_KEY_VIOLATION]: () =>
    'This operation would break a relationship with other data.',

  [ErrorCode.DATABASE_ERROR]: () =>
    'A database error occurred. Please try again.',

  [ErrorCode.INTERNAL_ERROR]: () =>
    'Something went wrong. Please try again later.',
};

/**
 * Format a snake_case field name for display.
 * Strips a trailing `_id`, replaces underscores with spaces, and
 * title-cases each word.
 *
 * @param {?string} field - Raw field name from the backend, e.g. `"party_id"`.
 * @returns {string} Human-readable label, e.g. `"Party"`. Returns
 *          `"This field"` when `field` is falsy.
 * @private
 */
function formatField(field) {
  if (!field) return 'This field';
  return field
    .replace(/_id$/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Normalize any error-ish value into a {@link ParsedError}.
 *
 * Accepts:
 *  - An Axios-style error (`error.response.data.error`)
 *  - A fetch `Response` (body is read as JSON; safe if unreadable)
 *  - An already-unwrapped `{ success: false, error: {...} }` object
 *  - A raw error object that already has a `code`
 *
 * Unknown shapes fall back to `INTERNAL_ERROR` / status `500`.
 *
 * @async
 * @param {Error|Response|Object} error - The value to normalize.
 * @returns {Promise<ParsedError>} Structured error suitable for
 *          {@link getUserMessage} and UI consumption.
 */
export async function parseApiError(error) {
  let errorData = null;
  let status = 500;

  // Handle different error shapes
  if (error?.response) {
    // Axios error
    status = error.response.status;
    errorData = error.response.data?.error;
  } else if (error instanceof Response) {
    // Fetch Response
    status = error.status;
    try {
      const json = await error.json();
      errorData = json.error;
    } catch {
      errorData = null;
    }
  } else if (error?.error) {
    // Already parsed { success: false, error: {...} }
    errorData = error.error;
    status = errorData?.status_code || 400;
  } else if (error?.code) {
    // Raw error object
    errorData = error;
  }

  // Build the parsed error
  const parsed = {
    code: errorData?.code || ErrorCode.INTERNAL_ERROR,
    message: errorData?.message || error?.message || 'An unexpected error occurred',
    field: errorData?.field || null,
    entity: errorData?.entity || null,
    details: errorData?.details || {},
    status,
    raw: errorData,
  };

  return parsed;
}

/**
 * Resolve a user-facing message for a parsed error.
 *
 * Resolution order:
 *  1. Template in {@link ERROR_MESSAGES} for `parsedError.code`
 *  2. The server-provided `parsedError.message` (if not the generic default)
 *  3. `"<fallbackContext> failed. Please try again."`
 *  4. A generic `"An error occurred. Please try again."`
 *
 * @param {ParsedError} parsedError - Output from {@link parseApiError}.
 * @param {string} [fallbackContext]
 *        Short description of the attempted action, used only when no
 *        specific message can be derived (e.g. `"Creating category"`).
 * @returns {string} Message safe to display to end users.
 */
export function getUserMessage(parsedError, fallbackContext) {
  const mapper = ERROR_MESSAGES[parsedError.code];

  if (mapper) {
    try {
      return mapper(parsedError);
    } catch {
      // Mapper threw — fall through to message
    }
  }

  // Fallback to server message or generic
  if (parsedError.message && parsedError.message !== 'An unexpected error occurred') {
    return parsedError.message;
  }

  return fallbackContext
    ? `${fallbackContext} failed. Please try again.`
    : 'An error occurred. Please try again.';
}

/**
 * Convenience wrapper: {@link parseApiError} + {@link getUserMessage}.
 *
 * @async
 * @param {Error|Response|Object} error - Any error-ish value.
 * @param {string} [fallbackContext] - See {@link getUserMessage}.
 * @returns {Promise<string>} User-facing message.
 */
export async function getErrorMessage(error, fallbackContext) {
  const parsed = await parseApiError(error);
  return getUserMessage(parsed, fallbackContext);
}

/**
 * Test whether a parsed error carries a specific backend error code.
 *
 * @param {ParsedError} parsedError
 * @param {string} code - One of {@link ErrorCode}.
 * @returns {boolean}
 */
export function isErrorCode(parsedError, code) {
  return parsedError.code === code;
}

/**
 * Test whether an error represents a missing resource
 * (`NOT_FOUND` code or HTTP 404).
 *
 * @param {ParsedError} parsedError
 * @returns {boolean}
 */
export function isNotFound(parsedError) {
  return parsedError.code === ErrorCode.NOT_FOUND || parsedError.status === 404;
}

/**
 * Test whether an error represents a uniqueness conflict
 * (`DUPLICATE_NAME` code or HTTP 409).
 *
 * @param {ParsedError} parsedError
 * @returns {boolean}
 */
export function isDuplicate(parsedError) {
  return parsedError.code === ErrorCode.DUPLICATE_NAME || parsedError.status === 409;
}