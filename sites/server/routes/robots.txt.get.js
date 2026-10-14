import { resolveSite } from '~~/lib/resolve-site.js'

export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  const url = getRequestURL(event)
  const target = resolveSite(url.host, '/', config.public.sitesBaseDomain)
  setHeader(event, 'content-type', 'text/plain; charset=utf-8')
  const sitemap = target.kind === 'subdomain' || target.kind === 'custom' ? `\nSitemap: ${url.origin}/sitemap.xml` : ''
  return `User-agent: *\nAllow: /${sitemap}\n`
})
