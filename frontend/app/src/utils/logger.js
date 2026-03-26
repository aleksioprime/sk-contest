const isEnabled = import.meta.env.VITE_LOGGER === 'true'

const logger = {
  log(...args) {
    if (isEnabled) console.log('[LOG]', ...args)
  },
  warn(...args) {
    if (isEnabled) console.warn('[WARN]', ...args)
  },
  error(...args) {
    // Ошибки показываем всегда
    console.error('[ERROR]', ...args)
  },
  debug(...args) {
    if (isEnabled) console.debug('[DEBUG]', ...args)
  },
}

export default logger
