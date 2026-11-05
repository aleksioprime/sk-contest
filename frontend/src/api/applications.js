import { http } from './http'

export const APP_STATUS_LABELS = {
  requested: 'Ждёт подтверждения',
  draft: 'Заполняется',
  submitted: 'На рассмотрении',
  needs_changes: 'Нужны правки',
  accepted: 'Принята',
  rejected: 'Отклонена',
  withdrawn: 'Отозвана',
}

export const APP_STATUS_TONES = {
  requested: 'warning',
  draft: 'neutral',
  submitted: 'brand',
  needs_changes: 'warning',
  accepted: 'success',
  rejected: 'danger',
  withdrawn: 'neutral',
}

export const SOURCE_LABELS = {
  form: 'Открытая форма',
  webhook: 'Внешняя форма',
  cabinet: 'Личный кабинет',
  staff: 'Оргкомитет',
  import: 'Архив',
}

export const PERSON_KIND_LABELS = { student: 'Ученик', employee: 'Сотрудник', external: 'Внешний участник' }

/** Кнопки модератора для решений, которые разрешил сервер (allowed_decisions). */
export const DECISION_ACTIONS = {
  confirmed: { label: 'Подтвердить и пригласить', variant: 'primary' },
  accepted: { label: 'Принять', variant: 'primary' },
  needs_changes: { label: 'Вернуть на доработку', variant: 'secondary' },
  rejected: { label: 'Отклонить', variant: 'danger' },
  submitted: { label: 'Вернуть на рассмотрение', variant: 'ghost' },
  requested: { label: 'Вернуть на подтверждение', variant: 'ghost' },
  draft: { label: 'Вернуть к заполнению', variant: 'ghost' },
}

/** Встроенные поля первого шага, которые организатор может включить в открытой форме. */
export const ASKABLE_FIELDS = {
  phone: 'Телефон',
  organization: 'Школа или организация',
  grade: 'Класс',
  title: 'Название работы',
  direction: 'Направление',
  participation_form: 'Форма участия',
}

export async function fetchOpenEvents() {
  return (await http.get('/v1/public/events')).data
}

export async function fetchPublicForm(slug) {
  return (await http.get(`/v1/public/events/${slug}/form`)).data
}

export async function fetchMyApplications() {
  return (await http.get('/v1/my/applications')).data
}

/** Общая заявка: для вошедшего пользователя сервер подставит данные учётной записи. */
export async function registerForEvent(slug, payload) {
  return (await http.post(`/v1/public/events/${slug}/register`, payload)).data
}

export async function fetchApplication(id) {
  return (await http.get(`/v1/applications/${id}`)).data
}

export async function saveApplication(id, payload) {
  return (await http.put(`/v1/applications/${id}`, payload)).data
}

export async function submitApplication(id) {
  return (await http.post(`/v1/applications/${id}/submit`)).data
}

export async function withdrawApplication(id) {
  return (await http.post(`/v1/applications/${id}/withdraw`)).data
}

export async function uploadFile(file, purpose = 'document') {
  const body = new FormData()
  body.append('file', file)
  body.append('purpose', purpose)
  return (await http.post('/v1/files', body, { headers: { 'Content-Type': 'multipart/form-data' } })).data
}

export async function fetchEventApplications(eventId, params) {
  return (await http.get(`/v1/events/${eventId}/applications`, { params })).data
}

export async function decide(id, status, comment = '') {
  return (await http.post(`/v1/applications/${id}/decision`, { status, comment })).data
}

export async function decideMany(eventId, ids, status, comment = '') {
  return (await http.post(`/v1/events/${eventId}/applications/decision`, { ids, status, comment })).data
}

export function exportUrl(eventId, onlyAccepted = false) {
  return `/api/v1/events/${eventId}/applications/export.xlsx${onlyAccepted ? '?only_accepted=true' : ''}`
}

export async function fetchForm(eventId) {
  return (await http.get(`/v1/events/${eventId}/form`)).data
}

export async function saveForm(eventId, form) {
  return (await http.put(`/v1/events/${eventId}/form`, form)).data
}

export async function resetForm(eventId) {
  return (await http.post(`/v1/events/${eventId}/form/reset`)).data
}

/** Ошибки полей из ответа 422 с detail.errors. */
export function fieldErrors(error) {
  const detail = error?.response?.data?.detail
  return detail && typeof detail === 'object' && !Array.isArray(detail) ? detail.errors ?? {} : {}
}

/** Видно ли поле анкеты при текущих ответах (условие visible_if). */
export function isVisible(field, answers) {
  if (!field.visible_if) return true
  const value = answers[field.visible_if.field]
  return value === field.visible_if.equals || (Array.isArray(value) && value.includes(field.visible_if.equals))
}

/** Заявка от оргкомитета: пустая, заполняется в карточке заявки. */
export async function createStaffApplication(eventId, payload) {
  return (await http.post(`/v1/events/${eventId}/applications/manual`, payload)).data
}

export async function manageApplication(id, payload) {
  return (await http.put(`/v1/applications/${id}/manage`, payload)).data
}

// --- Заявитель и человек из базы

export async function fetchMatches(id) {
  return (await http.get(`/v1/applications/${id}/matches`)).data
}

export async function searchPeople(eventId, q) {
  return (await http.get(`/v1/events/${eventId}/people`, { params: { q } })).data
}

export async function linkPerson(id, personId) {
  return (await http.put(`/v1/applications/${id}/person`, { person_id: personId })).data
}

export async function unlinkPerson(id) {
  return (await http.delete(`/v1/applications/${id}/person`)).data
}

export async function updateContact(id, contact) {
  return (await http.put(`/v1/applications/${id}/contact`, contact)).data
}

export async function resendInvitation(id) {
  return (await http.post(`/v1/applications/${id}/invite`)).data
}

// --- Вебхук мероприятия

export async function fetchWebhook(eventId) {
  return (await http.get(`/v1/events/${eventId}/webhook`)).data.url
}

export async function enableWebhook(eventId) {
  return (await http.post(`/v1/events/${eventId}/webhook`)).data.url
}

export async function disableWebhook(eventId) {
  await http.delete(`/v1/events/${eventId}/webhook`)
}
