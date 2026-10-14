const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']

export function formatDate(value) {
  if (!value) return ''
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return `${day} ${MONTHS[month - 1]} ${year}`
}

/** «12–14 марта 2027», «12 марта – 18 апреля 2027», «28 декабря 2026 – 10 января 2027». */
export function formatRange(start, end) {
  if (!start) return ''
  if (!end || end === start) return formatDate(start)
  const [y1, m1] = start.split('-')
  const [y2, m2] = end.split('-')
  if (y1 === y2 && m1 === m2) return `${Number(start.slice(8, 10))}–${formatDate(end)}`
  if (y1 === y2) return `${formatDate(start).replace(` ${y1}`, '')} – ${formatDate(end)}`
  return `${formatDate(start)} – ${formatDate(end)}`
}
