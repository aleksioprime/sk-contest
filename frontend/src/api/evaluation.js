import axios from 'axios'
import { http } from './http'

export const SHEET_STATUS_LABELS = { draft: 'Черновик', active: 'Идёт оценка', closed: 'Закрыт' }
export const SHEET_STATUS_TONES = { draft: 'neutral', active: 'success', closed: 'score' }
export const SHEET_MODE_LABELS = { jury: 'Жюри', anonymous: 'Зрители по QR', mixed: 'Жюри и зрители' }
export const AGGREGATE_LABELS = { avg: 'Среднее', sum: 'Сумма', median: 'Медиана' }
export const RANK_LABELS = { competition: '1, 1, 3', dense: '1, 1, 2' }

// Шкалы и таблицы
export const fetchScales = async (eventId) => (await http.get(`/v1/events/${eventId}/scales`)).data
export const createScale = async (eventId, data) => (await http.post(`/v1/events/${eventId}/scales`, data)).data
export const updateScale = async (id, data) => (await http.put(`/v1/scales/${id}`, data)).data
export const deleteScale = async (id) => http.delete(`/v1/scales/${id}`)
export const fetchScorecards = async (eventId) => (await http.get(`/v1/events/${eventId}/scorecards`)).data
export const createScorecard = async (eventId, data) => (await http.post(`/v1/events/${eventId}/scorecards`, data)).data
export const updateScorecard = async (id, data) => (await http.put(`/v1/scorecards/${id}`, data)).data
export const copyScorecard = async (id) => (await http.post(`/v1/scorecards/${id}/copy`)).data
export const deleteScorecard = async (id) => http.delete(`/v1/scorecards/${id}`)

// Листы
export const fetchSheets = async (eventId) => (await http.get(`/v1/events/${eventId}/sheets`)).data
export const createSheet = async (eventId, data) => (await http.post(`/v1/events/${eventId}/sheets`, data)).data
export const fetchSheet = async (id) => (await http.get(`/v1/sheets/${id}`)).data
export const updateSheet = async (id, data) => (await http.patch(`/v1/sheets/${id}`, data)).data
export const deleteSheet = async (id) => http.delete(`/v1/sheets/${id}`)
export const addWorks = async (id, data) => (await http.post(`/v1/sheets/${id}/works`, data)).data
export const removeWork = async (id, workId) => (await http.delete(`/v1/sheets/${id}/works/${workId}`)).data
export const setJudges = async (id, judges, force = false) => (await http.put(`/v1/sheets/${id}/judges`, { judges, force })).data
export const setJudgeAccess = async (id, userId, open) => (await http.post(`/v1/sheets/${id}/judges/${userId}/access`, { open })).data
export const issueJudgeCards = async (id, userIds = null) => (await http.post(`/v1/sheets/${id}/judge-cards`, { user_ids: userIds })).data

export const searchUsers = async (eventId, q) => (await http.get(`/v1/events/${eventId}/user-search`, { params: { q } })).data

/** Судьи листа в формате запроса: существующие — по id, новые — с ФИО, email и паролем. */
export const judgesPayload = (judges) => judges.map((j) => (j.user_id ? { user_id: j.user_id } : j))
export const distribute = async (id, mode, perWork) => (await http.post(`/v1/sheets/${id}/distribute`, { mode, per_work: perWork })).data
export const remindJudges = async (id) => (await http.post(`/v1/sheets/${id}/remind`)).data

export const formatDeadline = (value) =>
  value ? new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) : ''
export const deadlinePassed = (value) => !!value && new Date(value) <= new Date()

/** ISO-дата → значение для <input type="datetime-local"> в часовом поясе браузера. */
export function toLocalInput(value) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

export const setSheetStatus = async (id, status) => (await http.post(`/v1/sheets/${id}/status`, { status })).data

// Судья
export const fetchMySheets = async () => (await http.get('/v1/my/sheets')).data
export const fetchMyWorks = async (sheetId) => (await http.get(`/v1/my/sheets/${sheetId}/works`)).data

/** Клиент оценки: судья по id оценки или зритель по токену работы. Одинаковый интерфейс для EvaluationForm. */
export function judgeClient(evaluationId) {
  const base = `/v1/evaluations/${evaluationId}`
  return {
    load: async () => (await http.get(base)).data,
    setCriterion: async (criterionId, value) => (await http.put(`${base}/criteria/${criterionId}`, value)).data,
    setComment: async (comment) => (await http.patch(base, { comment })).data,
  }
}

const publicHttp = axios.create({ baseURL: '/api', headers: { 'Content-Type': 'application/json' } })
const ANON_KEY = (token) => `ske-anon:${token}`

export function readAnonymousToken(token) {
  try {
    return localStorage.getItem(ANON_KEY(token))
  } catch {
    return null
  }
}

export function anonymousClient(token, anonToken) {
  const base = `/v1/public/evaluate/${token}`
  const headers = { 'X-Anonymous-Token': anonToken }
  return {
    load: async () => (await publicHttp.get(`${base}/evaluation`, { headers })).data,
    setCriterion: async (criterionId, value) => (await publicHttp.put(`${base}/criteria/${criterionId}`, value, { headers })).data,
    setComment: async (comment) => (await publicHttp.patch(`${base}/evaluation`, { comment }, { headers })).data,
  }
}

export async function fetchPublicWork(token) {
  return (await publicHttp.get(`/v1/public/evaluate/${token}`)).data
}

export async function startAnonymous(token, name) {
  const { data } = await publicHttp.post(`/v1/public/evaluate/${token}/start`, { name })
  try {
    localStorage.setItem(ANON_KEY(token), data.token)
  } catch {
    // без хранилища оценка сработает только в этой вкладке
  }
  return data
}

/** Адрес анонимной оценки работы для QR-кода. */
export function anonymousUrl(token) {
  return `${window.location.origin}/evaluate/${token}`
}

export function formatPoints(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}
