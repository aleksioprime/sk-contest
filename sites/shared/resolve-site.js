/**
 * Определяет, какой сайт открыт, по заголовку Host.
 *
 *   events.skolhub.ru/<slug>       → { kind: 'path', slug }
 *   <slug>.events.skolhub.ru       → { kind: 'subdomain', slug }
 *   любой другой домен             → { kind: 'custom', domain }
 *   events.skolhub.ru без пути     → { kind: 'root' }
 */

const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/
const RESERVED = new Set(['www', 'app', 'api', 'admin', 'static', 'mail'])

export function resolveSite(host, path, baseDomain) {
  const hostname = String(host || '')
    .toLowerCase()
    .replace(/:\d+$/, '')
  const base = baseDomain.toLowerCase()

  if (hostname === base || hostname === 'localhost' || hostname === '127.0.0.1') {
    const slug = String(path || '/').split('/').filter(Boolean)[0]
    return slug && isValidSlug(slug) ? { kind: 'path', slug } : { kind: 'root' }
  }

  if (hostname.endsWith(`.${base}`)) {
    const slug = hostname.slice(0, -(base.length + 1))
    if (isValidSlug(slug)) return { kind: 'subdomain', slug }
    return { kind: 'unknown' }
  }

  return hostname ? { kind: 'custom', domain: hostname } : { kind: 'unknown' }
}

export function isValidSlug(slug) {
  return SLUG_RE.test(slug) && !RESERVED.has(slug)
}
