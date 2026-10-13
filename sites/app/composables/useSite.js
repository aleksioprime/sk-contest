import { createBlockInstance, getBlock } from '@sk-events/blocks'
import { resolveSite } from '~~/shared/resolve-site.js'

/**
 * Опубликованный сайт для текущего запроса.
 * Этап 0: API сайтов ещё нет, поэтому для любого slug отдаётся демонстрационная страница.
 * На этапе 6 здесь будет запрос к /api/v1/sites/resolve.
 */
export function useSite() {
  const config = useRuntimeConfig()
  const url = useRequestURL()
  const target = resolveSite(url.host, url.pathname, config.public.sitesBaseDomain)

  if (target.kind === 'root' || target.kind === 'unknown') {
    return { target, site: null }
  }
  return { target, site: demoSite(target.slug ?? target.domain) }
}

function demoSite(name) {
  const hero = createBlockInstance(getBlock('hero'), 'hero')
  hero.props.eyebrow = 'Сайт мероприятия'
  hero.props.title = name
  hero.props.subtitle = 'Лендинг ещё не опубликован. Организатор соберёт его в конструкторе SK Events.'
  hero.props.ctaLabel = ''
  return {
    title: name,
    theme: {},
    event: {},
    page: { blocks: [hero] },
  }
}
