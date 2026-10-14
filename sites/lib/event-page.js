/**
 * Страница мероприятия по умолчанию, пока организатор не собрал лендинг в конструкторе (этап 6).
 * Собирается из блоков пакета @sk-events/blocks по публичным данным мероприятия.
 */
import { createBlockInstance, getBlock } from '@sk-events/blocks'

const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']

export function formatDate(value) {
  if (!value) return ''
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return `${day} ${MONTHS[month - 1]} ${year}`
}

export function formatRange(start, end) {
  if (!start) return ''
  if (!end || end === start) return formatDate(start)
  const [y1, m1] = start.split('-')
  const [y2, m2] = end.split('-')
  if (y1 === y2 && m1 === m2) return `${Number(start.slice(8, 10))}–${formatDate(end)}`
  if (y1 === y2) return `${formatDate(start).replace(` ${y1}`, '')} – ${formatDate(end)}`
  return `${formatDate(start)} – ${formatDate(end)}`
}

export function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

/** Обычный текст в абзацы HTML. Пустая строка разделяет абзацы. */
export function textToHtml(text) {
  return String(text ?? '')
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replaceAll('\n', '<br>')}</p>`)
    .join('')
}

const AWARDS = { winner: 'Победитель', prize: 'Призёр' }

export function buildEventPage(event, appUrl, results = []) {
  const blocks = []

  const hero = createBlockInstance(getBlock('hero'), 'hero')
  hero.props.title = event.title
  hero.props.subtitle = event.short_description
  hero.props.ctaLabel = event.registration_open ? 'Подать заявку' : ''
  hero.props.ctaHref = `${appUrl.replace(/\/$/, '')}/events/${event.slug}/apply`
  if (event.cover_url) {
    // Файлы отдаёт API на домене приложения
    hero.props.image = { url: `${appUrl.replace(/\/$/, '')}${event.cover_url}`, alt: '' }
    hero.variant = 'image-right'
  }
  blocks.push(hero)

  if (event.description) {
    const about = createBlockInstance(getBlock('text'), 'about')
    about.props.title = 'О мероприятии'
    about.props.body = textToHtml(event.description)
    blocks.push(about)
  }

  if (event.directions.length) {
    const directions = createBlockInstance(getBlock('text'), 'directions')
    directions.props.title = 'Направления'
    directions.props.body = `<ul>${event.directions
      .map((d) => `<li><strong>${escapeHtml(d.title)}</strong>${d.description ? ` — ${escapeHtml(d.description)}` : ''}</li>`)
      .join('')}</ul>`
    directions.common.background = 'muted'
    blocks.push(directions)
  }

  if (event.stages.length) {
    const stages = createBlockInstance(getBlock('text'), 'stages')
    stages.props.title = 'Этапы'
    stages.props.body = `<ul>${event.stages
      .map((s) => {
        const dates = formatRange(s.date_start, s.date_end)
        const kind = s.kind === 'remote' ? 'заочно' : 'очно'
        return `<li><strong>${escapeHtml(s.title)}</strong> · ${kind}${dates ? ` · ${dates}` : ''}</li>`
      })
      .join('')}</ul>`
    blocks.push(stages)
  }

  if (results.length) {
    const winners = createBlockInstance(getBlock('text'), 'results')
    winners.props.title = 'Победители и призёры'
    winners.props.body = results
      .map((group) => {
        const items = group.winners
          .map((w) => `<li><strong>${w.rank} место · ${AWARDS[w.award]}</strong> — ${escapeHtml(w.participants.join(', '))}, «${escapeHtml(w.title)}»</li>`)
          .join('')
        return `${group.direction ? `<h3>${escapeHtml(group.direction)}</h3>` : ''}<ul>${items}</ul>`
      })
      .join('')
    winners.common.background = 'accent'
    // Итоги — сразу после обложки: после публикации это главное на странице
    blocks.splice(1, 0, winners)
  }

  return {
    title: event.title,
    description: event.short_description,
    theme: {},
    event: { title: event.title, dates: formatRange(event.date_start, event.date_end), place: event.place },
    page: { blocks },
  }
}
