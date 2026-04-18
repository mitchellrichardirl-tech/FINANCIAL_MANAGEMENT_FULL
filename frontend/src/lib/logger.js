/**
 * @file logger.js
 * Lightweight namespaced console logger with env-driven level filtering.
 *
 * Each module creates its own logger via {@link createLogger}, which
 * prefixes every line with a timestamp and namespace, applies a per-level
 * CSS color in DevTools, and suppresses output below the configured
 * threshold.
 *
 * The active level is read once at import time from `VITE_LOG_LEVEL`,
 * defaulting to `'debug'` in dev (`import.meta.env.DEV`) and `'warn'`
 * otherwise.
 */

/**
 * A namespaced logger instance.
 * All methods accept the same variadic arguments as the underlying
 * `console.*` call and are no-ops when below the active threshold.
 *
 * @typedef {Object} Logger
 * @property {(...args: any[]) => void} debug - Verbose diagnostics; dev-only by default.
 * @property {(...args: any[]) => void} info  - Normal operational messages.
 * @property {(...args: any[]) => void} warn  - Recoverable / unexpected conditions.
 * @property {(...args: any[]) => void} error - Failures; always shown unless level is `'silent'`.
 */

/**
 * Valid log level names, in ascending severity.
 * `'silent'` suppresses all output.
 *
 * @typedef {'debug'|'info'|'warn'|'error'|'silent'} LogLevel
 */

/**
 * Numeric severity for each {@link LogLevel}. A message is emitted only
 * when its level value is `>=` {@link threshold}.
 *
 * @type {Record<LogLevel, number>}
 */
const LEVELS = { debug: 0, info: 1, warn: 2, error: 3, silent: 4 };

/**
 * Level name resolved from the environment.
 * Controlled via `.env` → `VITE_LOG_LEVEL`; defaults to `'debug'` in dev,
 * `'warn'` in prod.
 *
 * @type {string}
 */
const configuredLevel =
  import.meta.env.VITE_LOG_LEVEL || (import.meta.env.DEV ? 'debug' : 'warn');

/**
 * Minimum numeric severity that will be emitted.
 * Falls back to `warn` if `VITE_LOG_LEVEL` is set to an unrecognized value.
 *
 * @type {number}
 */
const threshold = LEVELS[configuredLevel] ?? LEVELS.warn;

/**
 * Determine whether a message at `level` should be written.
 *
 * @param {LogLevel} level
 * @returns {boolean} `true` if `level` meets or exceeds the active threshold.
 * @private
 */
function shouldLog(level) {
  return LEVELS[level] >= threshold;
}

/**
 * DevTools CSS applied to the `%c` prefix for each level.
 *
 * @type {Record<Exclude<LogLevel, 'silent'>, string>}
 */
const styles = {
  debug: 'color: #888',
  info:  'color: #0a7',
  warn:  'color: #e90',
  error: 'color: #d33; font-weight: bold',
};

/**
* Build the argument list passed to `console.*`.
 *
 * Produces `["%cHH:mm:ss.SSS [ns]", <css>, ...callerArgs]` so the
 * timestamp + namespace prefix is styled via the `%c` directive and the
 * caller's original arguments follow untouched (preserving object
 * expansion in DevTools).
 *
 * @param {Exclude<LogLevel, 'silent'>} level - Level whose style to apply.
 * @param {string} ns - Namespace label for the prefix.
 * @param {any[]} args - Original arguments passed to the logger method.
 * @returns {any[]} Arguments ready to spread into `console.<level>(...)`.
 * @private
 */
function fmt(level, ns, args) {
  const ts = new Date().toISOString().split('T')[1].slice(0, 12); // HH:mm:ss.SSS
  return [`%c${ts} [${ns}]`, styles[level], ...args];
}

/**
 * Create a namespaced {@link Logger}.
 *
 * The namespace is purely a display label — conventionally
 * `feature[:subarea]` — shown in every log line so output can be visually
 * grouped and filtered in DevTools.
 *
 * @param {string} ns - Namespace label, e.g. `'receipts:api'` or `'apiClient'`.
 * @returns {Logger} Logger bound to `ns` and the current level threshold.
 *
 * @example
 * const log = createLogger('receipts:api');
 * log.debug('fetching', { id });
 * log.error('upload failed', err);
 */
export function createLogger(ns) {
  return {
    debug: (...a) => shouldLog('debug') && console.debug(...fmt('debug', ns, a)),
    info:  (...a) => shouldLog('info')  && console.info(...fmt('info', ns, a)),
    warn:  (...a) => shouldLog('warn')  && console.warn(...fmt('warn', ns, a)),
    error: (...a) => shouldLog('error') && console.error(...fmt('error', ns, a)),
  };
}