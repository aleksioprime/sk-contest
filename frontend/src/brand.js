/** Название сервиса и семейство продуктов гимназии — для шапки, футера и заголовков вкладок. */
export const SERVICE = 'contest'

export const SCHOOL = { name: 'Гимназия Сколково', genitive: 'Гимназии Сколково', url: 'https://gymnasium.sk.ru/' }

export const PRODUCTS = [
  { key: 'contest', name: 'Конкурсы', url: 'https://contest.skolhub.ru/' },
  { key: 'survey', name: 'Опросы', url: 'https://survey.skolhub.ru/' },
  { key: 'diagnostic', name: 'Диагностика', url: 'https://diagnostic.skolhub.ru/' },
]

export const SERVICE_NAME = PRODUCTS.find((p) => p.key === SERVICE).name

/** Заголовок вкладки: «Страница — Конкурсы · Гимназия Сколково» */
export function pageTitle(page = '') {
  const base = `${SERVICE_NAME} · ${SCHOOL.name}`
  return page ? `${page} — ${base}` : base
}
