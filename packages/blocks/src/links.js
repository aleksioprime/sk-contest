const SAFE = /^(https?:\/\/|mailto:|tel:|#|\/(?!\/))/i

/** Ссылка только безопасных видов, иначе пустая. */
export function safeHref(value) {
  const href = String(value ?? '').trim()
  return SAFE.test(href) ? href : ''
}

/** Файлы API лежат на домене приложения, лендинг может быть на другом домене. */
export function assetUrl(data, asset) {
  const url = typeof asset === 'string' ? asset : asset?.url
  if (!url) return ''
  if (url.startsWith('/api/')) return `${(data?.assetBase ?? '').replace(/\/$/, '')}${url}`
  return safeHref(url)
}
