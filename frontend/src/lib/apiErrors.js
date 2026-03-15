/**
 * Error codes returned by the backend.
 * Keep in sync with src/api/utils/errors.py → ErrorCode
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
 * User-friendly message templates for each error code.
 * Functions receive the parsed error object for interpolation.
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
 * Format a field name for display (e.g., "party_id" → "Party")
 */
function formatField(field) {
  if (!field) return 'This field';
  return field
    .replace(/_id$/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Parse an API error response into a structured object.
 *
 * @param {Error|Response|Object} error - Axios error, fetch Response, or raw object
 * @returns {ParsedError}
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
 * Get a user-friendly message for a parsed error.
 *
 * @param {ParsedError} parsedError - Output from parseApiError
 * @param {string} [fallbackContext] - Context for generic errors (e.g., "Creating category")
 * @returns {string}
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
 * Convenience: parse and get message in one call.
 */
export async function getErrorMessage(error, fallbackContext) {
  const parsed = await parseApiError(error);
  return getUserMessage(parsed, fallbackContext);
}

/**
 * Check if an error is a specific code.
 */
export function isErrorCode(parsedError, code) {
  return parsedError.code === code;
}

/**
 * Check if error is a "not found" type (404).
 */
export function isNotFound(parsedError) {
  return parsedError.code === ErrorCode.NOT_FOUND || parsedError.status === 404;
}

/**
 * Check if error is a duplicate/conflict (409).
 */
export function isDuplicate(parsedError) {
  return parsedError.code === ErrorCode.DUPLICATE_NAME || parsedError.status === 409;
}