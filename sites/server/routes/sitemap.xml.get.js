import { pageUrl, resolveSite, siteApiPath } from '~~/lib/resolve-site.js'

/** Страницы опубликованного сайта для поисковиков. На общем домене sitemap нет. */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const url = getRequestURL(event)
  const target = resolveSite(url.host, '/', config.public.sitesBaseDomain)
  if (target.kind !== 'subdomain' && target.kind !== 'custom') {
    throw createError({ statusCode: 404, statusMessage: 'Не найдено' })
  }
  const payload = await $fetch(siteApiPath(target), { baseURL: config.apiInternalUrl }).catch(() => null)
  if (!payload) throw createError({ statusCode: 404, statusMessage: 'Не найдено' })
  const pages = payload.content?.pages ?? [{ path: '' }]
  const urls = pages.map((page) => `  <url><loc>${pageUrl(target, url.origin, page.path)}</loc></url>`).join('\n')
  setHeader(event, 'content-type', 'application/xml; charset=utf-8')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
})
