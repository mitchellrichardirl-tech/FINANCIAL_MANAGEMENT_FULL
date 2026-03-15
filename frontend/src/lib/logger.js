const LEVELS = { debug: 0, info: 1, warn: 2, error: 3, silent: 4 };

// Controlled via .env — defaults to debug in dev, warn in prod
const configuredLevel =
  import.meta.env.VITE_LOG_LEVEL || (import.meta.env.DEV ? 'debug' : 'warn');
const threshold = LEVELS[configuredLevel] ?? LEVELS.warn;

function shouldLog(level) {
  return LEVELS[level] >= threshold;
}

function fmt(level, ns, args) {
  const ts = new Date().toISOString().split('T')[1].slice(0, 12); // HH:mm:ss.SSS
  return [`%c${ts} [${ns}]`, styles[level], ...args];
}

const styles = {
  debug: 'color: #888',
  info:  'color: #0a7',
  warn:  'color: #e90',
  error: 'color: #d33; font-weight: bold',
};

/**
 * Create a namespaced logger.
 * @example const log = createLogger('receipts:api');
 */
export function createLogger(ns) {
  return {
    debug: (...a) => shouldLog('debug') && console.debug(...fmt('debug', ns, a)),
    info:  (...a) => shouldLog('info')  && console.info(...fmt('info', ns, a)),
    warn:  (...a) => shouldLog('warn')  && console.warn(...fmt('warn', ns, a)),
    error: (...a) => shouldLog('error') && console.error(...fmt('error', ns, a)),
  };
}