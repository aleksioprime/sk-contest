/**
 * Определяет, какой сайт и какая его страница открыты, по заголовку Host и пути.
 *
 *   events.skolhub.ru/<slug>/<page>  → { kind: 'path', slug, page }
 *   <slug>.events.skolhub.ru/<page>  → { kind: 'subdomain', slug, page }
 *   свой домен/<page>                → { kind: 'custom', domain, page }
 *   events.skolhub.ru без пути       → { kind: 'root' }
 */

const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/
const RESERVED = new Set(['www', 'app', 'api', 'admin', 'static', 'mail', 'sites'])

function segments(path) {
  return String(path || '/')
    .split('?')[0]
    .split('/')
    .filter(Boolean)
}

export function resolveSite(host, path, baseDomain) {
  const hostname = String(host || '')
    .toLowerCase()
    .replace(/:\d+$/, '')
  const base = baseDomain.toLowerCase()
  const parts = segments(path)

  if (hostname === base || hostname === 'localhost' || hostname === '127.0.0.1') {
    const [slug, page = ''] = parts
    return slug && isValidSlug(slug) ? { kind: 'path', slug, page } : { kind: 'root' }
  }

  if (hostname.endsWith(`.${base}`)) {
    const slug = hostname.slice(0, -(base.length + 1))
    if (isValidSlug(slug)) return { kind: 'subdomain', slug, page: parts[0] ?? '' }
    return { kind: 'unknown' }
  }

  return hostname ? { kind: 'custom', domain: hostname, page: parts[0] ?? '' } : { kind: 'unknown' }
}

export function isValidSlug(slug) {
  return SLUG_RE.test(slug) && !RESERVED.has(slug)
}

/** Адрес страницы сайта для ссылок и sitemap. */
export function pageUrl(target, origin, page) {
  const prefix = target.kind === 'path' ? `/${target.slug}` : ''
  return `${origin}${prefix}/${page}`.replace(/\/+$/, '') || origin
}

/** API-адрес данных сайта для цели. */
export function siteApiPath(target) {
  if (target.kind === 'custom') return `/api/v1/public/sites/by-domain/${encodeURIComponent(target.domain)}`
  return `/api/v1/public/sites/by-slug/${target.slug}`
}
