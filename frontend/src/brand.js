/** Название сервиса и хаб приложений гимназии - для шапки, футера и заголовков вкладок. */
export const SERVICE_NAME = 'Конкурсы'

export const SCHOOL = { name: 'Гимназия Сколково', genitive: 'Гимназии Сколково', url: 'https://gymnasium.sk.ru/' }

/** Хаб приложений гимназии: все платформы и сервисы на одной странице */
export const HUB = { name: 'Приложения Гимназии Сколково', url: 'https://skolhub.ru/' }

/** Заголовок вкладки: «Страница - Конкурсы · Гимназия Сколково» */
export function pageTitle(page = '') {
  const base = `${SERVICE_NAME} · ${SCHOOL.name}`
  return page ? `${page} - ${base}` : base
}
