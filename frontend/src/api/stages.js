import { http } from './http'

export const STAGE_STATUS_LABELS = {
  admitted: 'Допущен',
  scheduled: 'Назначена защита',
  evaluated: 'Оценён',
  passed: 'Прошёл',
  not_passed: 'Не прошёл',
  withdrawn: 'Снят',
}

export const STAGE_STATUS_TONES = {
  admitted: 'neutral',
  scheduled: 'brand',
  evaluated: 'score',
  passed: 'success',
  not_passed: 'danger',
  withdrawn: 'neutral',
}

export const AWARD_LABELS = { winner: 'Победитель', prize: 'Призёр', participant: 'Участник' }
export const AWARD_TONES = { winner: 'score', prize: 'brand', participant: 'neutral' }

export const fetchStage = async (eventId, stageId) => (await http.get(`/v1/events/${eventId}/stages/${stageId}`)).data
export const admitToStage = async (eventId, stageId) => (await http.post(`/v1/events/${eventId}/stages/${stageId}/admit`)).data
export const setStageRule = async (eventId, stageId, rule) => (await http.put(`/v1/events/${eventId}/stages/${stageId}/rule`, rule)).data
export const applyAdvance = async (eventId, stageId, decisions) =>
  (await http.post(`/v1/events/${eventId}/stages/${stageId}/advance`, { decisions })).data
export const updateParticipant = async (id, changes) => (await http.patch(`/v1/stage-participants/${id}`, changes)).data
export const addSlot = async (eventId, stageId, slot) => (await http.post(`/v1/events/${eventId}/stages/${stageId}/slots`, slot)).data
export const deleteSlot = async (id) => http.delete(`/v1/slots/${id}`)
export const programUrl = (eventId, stageId) => `/api/v1/events/${eventId}/stages/${stageId}/program.xlsx`

export const fetchResults = async (eventId) => (await http.get(`/v1/events/${eventId}/results`)).data
export const saveAwards = async (eventId, awards) => (await http.put(`/v1/events/${eventId}/awards`, awards)).data
export const publishResults = async (eventId, published) =>
  (await http.post(`/v1/events/${eventId}/results/publish`, null, { params: { published } })).data
export const diplomasUrl = (eventId) => `/api/v1/events/${eventId}/diplomas.pdf`
export const diplomaUrl = (applicationId) => `/api/v1/applications/${applicationId}/diploma.pdf`
export const fetchMyResults = async () => (await http.get('/v1/my/results')).data
