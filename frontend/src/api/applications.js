import { http } from './http'

export const APP_STATUS_LABELS = {
  draft: 'Черновик',
  submitted: 'На рассмотрении',
  needs_changes: 'Нужны правки',
  accepted: 'Принята',
  rejected: 'Отклонена',
  withdrawn: 'Отозвана',
}

export const APP_STATUS_TONES = {
  draft: 'neutral',
  submitted: 'brand',
  needs_changes: 'warning',
  accepted: 'success',
  rejected: 'danger',
  withdrawn: 'neutral',
}

export async function fetchPublicForm(slug) {
  return (await http.get(`/v1/public/events/${slug}/form`)).data
}

export async function fetchMyApplications() {
  return (await http.get('/v1/my/applications')).data
}

export async function startApplication(slug) {
  return (await http.post(`/v1/events/${slug}/applications`)).data
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
