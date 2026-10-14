import { buildSite } from '~~/lib/site.js'
import { pageUrl, resolveSite, siteApiPath } from '~~/lib/resolve-site.js'

/**
 * Сайт для текущего запроса: определяется по Host и пути.
 * Данные кэшируются в API (Redis) и сбрасываются при публикации сайта или итогов.
 */
export async function useSite() {
  const config = useRuntimeConfig()
  const url = useRequestURL()
  const target = resolveSite(url.host, url.pathname, config.public.sitesBaseDomain)

  if (target.kind === 'root') return { target, site: null }
  if (target.kind === 'unknown') throw createError({ statusCode: 404, statusMessage: 'Сайт не найден' })

  // Сайт собирается один раз на сервере и передаётся в браузер как есть: гидратация совпадает.
  // Один useAsyncData: после await контекст Nuxt теряется
  const { data, error } = await useAsyncData(`site:${url.host}${url.pathname}`, async () => {
    const payload = await $fetch(siteApiPath(target), { baseURL: config.apiInternalUrl })
    return buildSite(payload, { appUrl: config.public.appUrl, page: target.page }) ?? { missing: true }
  })
  if (error.value || !data.value) {
    throw createError({ statusCode: 404, statusMessage: 'Мероприятие не найдено' })
  }
  if (data.value.missing) throw createError({ statusCode: 404, statusMessage: 'Страница не найдена' })
  const site = { ...data.value }

  // Основной адрес — свой домен, если подключён: поисковики не увидят дублей
  const canonicalOrigin = site.domain ? `https://${site.domain}` : url.origin
  const canonicalTarget = site.domain ? { kind: 'custom' } : target
  site.canonical = pageUrl(canonicalTarget, canonicalOrigin, target.page)
  site.links = Object.fromEntries(site.pages.map((p) => [p.path, pageUrl(target, '', p.path) || '/']))
  return { target, site }
}
