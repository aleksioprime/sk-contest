import { buildEventPage } from '~~/lib/event-page.js'
import { resolveSite } from '~~/lib/resolve-site.js'

/**
 * Сайт для текущего запроса: определяется по Host и пути, данные — из публичного API мероприятия.
 * Свои домены подключаются на этапе 6, пока для них сайт не находится.
 */
export async function useSite() {
  const config = useRuntimeConfig()
  const url = useRequestURL()
  const target = resolveSite(url.host, url.pathname, config.public.sitesBaseDomain)

  if (target.kind === 'root') return { target, site: null }
  if (!target.slug) throw createError({ statusCode: 404, statusMessage: 'Сайт не найден' })

  const { data, error } = await useAsyncData(`event:${target.slug}`, () =>
    $fetch(`/api/v1/public/events/${target.slug}`, { baseURL: config.apiInternalUrl }),
  )
  if (error.value || !data.value) {
    throw createError({ statusCode: 404, statusMessage: 'Мероприятие не найдено' })
  }
  return { target, site: buildEventPage(data.value, config.public.appUrl) }
}
