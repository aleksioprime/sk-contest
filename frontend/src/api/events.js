import { http } from './http'

export const STATUS_LABELS = {
  draft: 'Черновик',
  registration: 'Регистрация',
  running: 'Идёт',
  results: 'Итоги',
  archived: 'Архив',
}

export const STATUS_TONES = {
  draft: 'neutral',
  registration: 'brand',
  running: 'success',
  results: 'score',
  archived: 'neutral',
}

export const ROLE_LABELS = {
  organizer: 'Организатор',
  moderator: 'Модератор заявок',
  judge: 'Судья',
  observer: 'Наблюдатель',
}

export const MODULE_LABELS = {
  landing: 'Лендинг',
  registration: 'Регистрация',
  stages: 'Этапы',
  evaluation: 'Оценивание',
  results: 'Итоги',
}

export const LEVEL_LABELS = {
  school: 'Школьный',
  municipal: 'Муниципальный',
  regional: 'Региональный',
  national: 'Всероссийский',
  international: 'Международный',
}

export const FORMAT_LABELS = { onsite: 'Очный', online: 'Онлайн', hybrid: 'Смешанный' }

export async function fetchEventTypes() {
  return (await http.get('/v1/events/types')).data
}

export async function fetchEvents(scope = 'mine') {
  return (await http.get('/v1/events', { params: { scope } })).data
}

export async function fetchEvent(id) {
  return (await http.get(`/v1/events/${id}`)).data
}

export async function createEvent(payload) {
  return (await http.post('/v1/events', payload)).data
}

export async function updateEvent(id, changes) {
  return (await http.patch(`/v1/events/${id}`, changes)).data
}

export async function changeStatus(id, status) {
  return (await http.post(`/v1/events/${id}/status`, { status })).data
}

export async function deleteEvent(id) {
  await http.delete(`/v1/events/${id}`)
}

export async function isSlugAvailable(slug, excludeId) {
  return (await http.get('/v1/events/slug-available', { params: { slug, exclude_id: excludeId } })).data.available
}

/** kind: directions | stages | forms */
export async function addChild(eventId, kind, payload) {
  return (await http.post(`/v1/events/${eventId}/${kind}`, payload)).data
}

export async function updateChild(eventId, kind, childId, payload) {
  return (await http.patch(`/v1/events/${eventId}/${kind}/${childId}`, payload)).data
}

export async function deleteChild(eventId, kind, childId) {
  await http.delete(`/v1/events/${eventId}/${kind}/${childId}`)
}

export async function reorderChildren(eventId, kind, ids) {
  await http.put(`/v1/events/${eventId}/${kind}/order`, { ids })
}

export async function fetchMembers(eventId) {
  return (await http.get(`/v1/events/${eventId}/members`)).data
}

export async function addMember(eventId, email, role) {
  return (await http.post(`/v1/events/${eventId}/members`, { email, role })).data
}

export async function removeMember(eventId, memberId) {
  await http.delete(`/v1/events/${eventId}/members/${memberId}`)
}

/** Адрес из названия: транслитерация, нижний регистр, дефисы. */
export function slugify(title) {
  const map = {
    а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z', и: 'i', й: 'y', к: 'k', л: 'l',
    м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'ts', ч: 'ch', ш: 'sh',
    щ: 'sch', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
  }
  return title
    .toLowerCase()
    .split('')
    .map((ch) => map[ch] ?? ch)
    .join('')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 63)
    .replace(/-+$/g, '')
}
