/**
 * Данные мероприятия для блоков. Один формат для лендинга (sites) и превью в редакторе.
 * На входе — ответ API `/public/sites/...` или `/events/{id}/site/data`.
 */
import { formatRange } from './format.js'

export function buildSiteData(payload = {}, { appUrl = '', editing = false } = {}) {
  const event = payload.event ?? {}
  const base = appUrl.replace(/\/$/, '')
  return {
    editing,
    appUrl: base,
    assetBase: base,
    event: {
      title: event.title ?? '',
      slug: event.slug ?? '',
      type: event.type ?? '',
      shortDescription: event.short_description ?? '',
      dates: formatRange(event.date_start, event.date_end),
      place: event.place ?? '',
      format: event.format ?? '',
      cover: event.cover_url ? { url: event.cover_url, alt: '' } : null,
    },
    registration: {
      open: !!event.registration_open,
      opensAt: event.registration_opens_at ?? null,
      closesAt: event.registration_closes_at ?? null,
      url: event.slug ? `${base}/events/${event.slug}/apply` : '',
    },
    stages: (event.stages ?? []).map((s) => ({
      title: s.title,
      kind: s.kind,
      dates: formatRange(s.date_start, s.date_end),
      dateStart: s.date_start,
    })),
    directions: (event.directions ?? []).map((d) => ({ title: d.title, description: d.description ?? '' })),
    results: payload.results ?? [],
    program: payload.program ?? [],
    stats: payload.stats ?? {},
    menu: [],
  }
}

/** Фаза для правил показа блоков. */
export function sitePhase(payload = {}) {
  if ((payload.results ?? []).length) return 'results'
  return payload.event?.registration_open ? 'registration' : 'always'
}
