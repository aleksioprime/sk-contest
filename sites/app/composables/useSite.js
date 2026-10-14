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

  // Один useAsyncData: после await контекст Nuxt теряется, второй вызов упал бы
  const { data, error } = await useAsyncData(`event:${target.slug}`, async () => {
    const options = { baseURL: config.apiInternalUrl }
    const [event, results] = await Promise.all([
      $fetch(`/api/v1/public/events/${target.slug}`, options),
      $fetch(`/api/v1/public/events/${target.slug}/results`, options).catch(() => []),
    ])
    return { event, results }
  })
  if (error.value || !data.value) {
    throw createError({ statusCode: 404, statusMessage: 'Мероприятие не найдено' })
  }
  return { target, site: buildEventPage(data.value.event, config.public.appUrl, data.value.results) }
}
