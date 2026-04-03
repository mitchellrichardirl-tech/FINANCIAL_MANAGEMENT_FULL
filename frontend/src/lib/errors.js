/**
 * @file errors.js
 * Application-level error type used across the frontend.
 *
 * {@link AppError} separates the technical `message` (for logs/devtools)
 * from a `userMessage` that is safe to render in toasts or inline UI, and
 * carries optional `status`, `context`, and `cause` for debugging.
 */

/**
 * Default user-facing messages keyed by HTTP status code.
 * Used as a fallback when an {@link AppError} is constructed with a
 * `status` but no explicit `userMessage`.
 *
 * @type {Object<number, string>}
 */
const STATUS_MESSAGES = {
  400: 'The request was invalid.',
  401: 'Your session has expired. Please log in again.',
  403: "You don't have permission to do this.",
  404: 'The requested resource was not found.',
  409: 'This conflicts with an existing record.',
  422: 'Please check your input and try again.',
  429: 'Too many requests. Please wait a moment.',
  500: 'Something went wrong on the server.',
  502: 'The server is temporarily unavailable.',
  503: 'The server is temporarily unavailable.',
};

/**
 * Base error type for the frontend application.
 *
 * Thrown for client-side failures (e.g. network unreachable) and as a
 * general-purpose wrapper when rethrowing lower-level errors with a
 * user-safe message attached.
 *
 * @extends Error
 *
 * @example
 * throw new AppError({
 *   message: `fetch failed: ${err.message}`,
 *   userMessage: 'Unable to reach the server.',
 *   cause: err,
 * });
 */
export class AppError extends Error {
  /**
   * @param {Object} init
   * @param {string} init.message
   *        Technical description for logs / developers.
   * @param {string} [init.userMessage]
   *        Message safe to show end users. If omitted, derived from
   *        `status` via {@link STATUS_MESSAGES}, else a generic fallback.
   * @param {number} [init.status]
   *        Associated HTTP status code, if applicable.
   * @param {*} [init.context]
   *        Arbitrary contextual data to aid debugging (request params, ids…).
   * @param {Error} [init.cause]
   *        Underlying error being wrapped.
   */
  constructor({ message, userMessage, status, context, cause }) {
    super(message);
    /** @type {'AppError'} */
    this.name = 'AppError';
    /** @type {string} Human-readable message intended for the UI. */
    this.userMessage = userMessage || STATUS_MESSAGES[status] || 'Something went wrong.';
    /** @type {?number} HTTP status code, or `null`. */
    this.status = status || null;
    /** @type {*} Optional debugging context. */
    this.context = context || null;
    /** @type {?Error} Wrapped underlying error. */
    this.cause = cause || null;
  }
}