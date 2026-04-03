/**
 * @file apiClient.js
 * Central HTTP client for communicating with the backend API.
 *
 * Wraps `fetch` with:
 *  - Base URL resolution from Vite env (`VITE_API_URL`)
 *  - Automatic JSON serialization (with FormData passthrough for uploads)
 *  - Structured logging of requests, responses, and failures
 *  - Normalized error handling via {@link AppError} (network) and
 *    {@link ApiError} (non-2xx responses parsed by `apiErrors.js`)
 */

import { createLogger } from './logger';
import { AppError } from './errors';
import { parseApiError, getUserMessage } from './apiErrors';

/**
 * Base URL for all API requests.
 * Resolved from the Vite env var `VITE_API_URL`, falling back to the
 * local dev server.
 *
 * @type {string}
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

/** @type {import('./logger').Logger} */
const logger = createLogger('apiClient');

/**
 * Perform an HTTP request against the backend API.
 *
 * Behavior:
 *  - If `body` is a `FormData` instance it is sent as-is and no
 *    `Content-Type` header is set (the browser adds the multipart boundary).
 *  - Otherwise, if `body` is defined, it is `JSON.stringify`'d and a
 *    `Content-Type: application/json` header is added (caller headers win
 *    on merge).
 *  - Network failures (fetch rejects) are wrapped in {@link AppError}.
 *  - Non-OK HTTP responses are parsed with {@link parseApiError}, enriched
 *    with a user-facing message, and thrown as {@link ApiError}.
 *
 * @async
 * @param {string} endpoint
 *        Path relative to {@link API_BASE_URL}, e.g. `'/transactions'`.
 * @param {Object} [options] - Request options.
 * @param {string} [options.method='GET'] - HTTP method.
 * @param {*} [options.body]
 *        Request body. `FormData` is passed through; anything else is
 *        JSON-encoded.
 * @param {Object<string, string>} [options.headers]
 *        Extra headers to merge into the request.
 * @param {...*} [options.rest]
 *        Any additional `fetch` init options (e.g. `signal`, `credentials`).
 * @returns {Promise<any>} The parsed JSON response body.
 * @throws {AppError} If the network request itself fails (no response).
 * @throws {ApiError} If the server responds with a non-2xx status.
 *
 * @example
 * // GET
 * const txns = await apiCall('/transactions?limit=50');
 *
 * @example
 * // POST JSON
 * const created = await apiCall('/categories', {
 *   method: 'POST',
 *   body: { name: 'Groceries' },
 * });
 *
 * @example
 * // File upload
 * const form = new FormData();
 * form.append('file', file);
 * await apiCall('/receipts/upload', { method: 'POST', body: form });
 */
export async function apiCall(endpoint, { method = 'GET', body, headers, ...rest } = {}) {
  const opts = { method, headers, ...rest };

  if (body instanceof FormData) {
    opts.body = body; // browser sets multipart boundary — don't touch headers
  } else if (body !== undefined) {
    opts.headers = { 'Content-Type': 'application/json', ...headers };
    opts.body = JSON.stringify(body);
  }

  logger.debug(`API call: ${method} ${endpoint}`);
  logger.debug('Request options:', opts);

  let response;

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, opts);
  } catch (err) {
    logger.error(`Network error during API call: ${method} ${endpoint}`, err);
    throw new AppError({
      message: `Network error: ${err.message}`,
      userMessage: 'Unable to reach the server. Check your connection and try again.',
      cause: err,
    });
  }

  if (!response.ok) {
    const parsed = await parseApiError(response);
    parsed.userMessage = getUserMessage(parsed, `API error during ${method} ${endpoint}`);
    logger.warn('API error', {
      endpoint,
      method,
      status: response.status,
      body: parsed.userMessage,
    });

    throw new ApiError(parsed);
  }

  const data = await response.json();
  logger.debug(`API response: ${method} ${endpoint}`, data);

  return data;
}

/**
 * Safely extract a payload from a (possibly enveloped) API response.
 *
 * Tries, in order:
 *  1. `response.data[key]`
 *  2. `response[key]`
 *  3. `response.data`
 *  4. `response` (returned unchanged)
 *
 * Useful when different endpoints wrap results as
 * `{ data: { items: [...] } }`, `{ items: [...] }`, or return the array
 * directly.
 *
 * @param {*} response - Raw value returned from {@link apiCall}.
 * @param {string} key - Property name expected to hold the payload.
 * @returns {*} The extracted value, or the original response if nothing matched.
 *
 * @example
 * const list = unwrap(await apiCall('/transactions'), 'transactions');
 */
export function unwrap(response, key) {
  if (response?.data?.[key] !== undefined) return response.data[key];
  if (response?.[key] !== undefined) return response[key];
  if (response?.data !== undefined) return response.data;
  return response;
}

/**
 * Error thrown when the API returns a non-2xx response.
 *
 * Wraps the structured error produced by {@link parseApiError} and exposes
 * its fields directly on the error instance so callers can branch on
 * `err.code`, `err.status`, etc., and surface `err.userMessage` in the UI.
 *
 * @extends Error
 */
class ApiError extends Error {
  /**
   * @param {import('./apiErrors').ParsedError} parsed
   *        Structured error from {@link parseApiError}. May already include
   *        a precomputed `userMessage`.
   */
  constructor(parsed) {
    super(parsed.message);
    /** @type {'ApiError'} */
    this.name = 'ApiError';
    /** @type {string} Backend error code (see {@link import('./apiErrors').ErrorCode}). */
    this.code = parsed.code;
    /** @type {?string} Offending field name, if the error is field-scoped. */
    this.field = parsed.field;
    /** @type {?string} Entity/resource name the error relates to. */
    this.entity = parsed.entity;
    /** @type {Object} Additional machine-readable details from the server. */
    this.details = parsed.details;
    /** @type {number} HTTP status code. */
    this.status = parsed.status;
    /** @type {string} Human-readable message safe to show end users. */
    this.userMessage = parsed.userMessage ?? getUserMessage(parsed); // reuse if already set
  }
}