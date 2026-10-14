/** Даты на лендинге: всегда по Москве, чтобы SSR и браузер показывали одно и то же. */

const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
const TZ = 'Europe/Moscow'

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

function parts(value) {
  const map = {}
  for (const { type, value: v } of new Intl.DateTimeFormat('ru-RU', {
    timeZone: TZ,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value))) {
    map[type] = v
  }
  return map
}

/** «12 марта, 18:00» */
export function formatDateTime(value) {
  if (!value) return ''
  const p = parts(value)
  return `${Number(p.day)} ${MONTHS[Number(p.month) - 1]}, ${p.hour}:${p.minute}`
}

export function formatTime(value) {
  if (!value) return ''
  const p = parts(value)
  return `${p.hour}:${p.minute}`
}

/** Ключ дня по Москве: 2027-04-18 */
export function dayKey(value) {
  const p = parts(value)
  return `${p.year}-${p.month.padStart(2, '0')}-${p.day.padStart(2, '0')}`
}

export function formatDay(key) {
  const [, month, day] = key.split('-').map(Number)
  return `${day} ${MONTHS[month - 1]}`
}
