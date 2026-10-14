/**
 * Сайт для рендера: опубликованная версия из конструктора или шаблон по типу мероприятия,
 * если организатор ещё ничего не опубликовал.
 */
import { assetUrl, buildSiteData, buildTemplate, sitePhase } from '@sk-events/blocks'

export function buildSite(payload, { appUrl, page = '' }) {
  const event = payload.event
  const content = payload.content ?? buildTemplate(event.type, event, { dataOnly: true })
  const current = content.pages.find((p) => p.path === page)
  if (!current) return null
  const data = buildSiteData(payload, { appUrl })
  const seo = content.seo ?? {}
  const image = seo.image ?? (event.cover_url ? { url: event.cover_url } : null)
  return {
    page: current,
    pages: content.pages,
    theme: content.theme ?? {},
    data,
    phase: sitePhase(payload),
    domain: payload.domain ?? null,
    seo: {
      title: [current.path ? current.title : '', seo.title || event.title].filter(Boolean).join(' · '),
      description: seo.description || event.short_description || '',
      image: image ? assetUrl(data, image) : '',
      favicon: content.theme?.favicon ? assetUrl(data, content.theme.favicon) : '',
      metrika: seo.metrika || '',
    },
  }
}
