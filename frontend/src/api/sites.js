import { http } from './http'

export const fetchSite = async (eventId) => (await http.get(`/v1/events/${eventId}/site`)).data
export const saveSite = async (eventId, content) => (await http.put(`/v1/events/${eventId}/site`, { content })).data
export const fetchSiteData = async (eventId) => (await http.get(`/v1/events/${eventId}/site/data`)).data
export const publishSite = async (eventId, note = '') => (await http.post(`/v1/events/${eventId}/site/publish`, { note })).data
export const unpublishSite = async (eventId) => (await http.post(`/v1/events/${eventId}/site/unpublish`)).data
export const fetchVersions = async (eventId) => (await http.get(`/v1/events/${eventId}/site/versions`)).data
export const restoreVersion = async (eventId, versionId) =>
  (await http.post(`/v1/events/${eventId}/site/versions/${versionId}/restore`)).data
export const addDomain = async (eventId, domain) => (await http.post(`/v1/events/${eventId}/site/domains`, { domain })).data
export const checkDomain = async (id) => (await http.post(`/v1/site-domains/${id}/check`)).data
export const deleteDomain = async (id) => (await http.delete(`/v1/site-domains/${id}`)).data

export const DOMAIN_STATUS = { pending: 'Ждёт настройки DNS', active: 'Работает', error: 'DNS изменился' }
export const DOMAIN_TONES = { pending: 'warning', active: 'success', error: 'danger' }

/** Ошибки сохранения сайта (422) с привязкой к блокам: «pages.0.blocks.3.props.title» → блок и поле. */
export function siteErrors(error, draft) {
  const detail = error?.response?.data?.detail
  if (!detail?.errors) return []
  return detail.errors.map((item) => {
    const match = item.where.match(/^pages\.(\d+)\.blocks\.(\d+)(?:\.props\.?(.*))?/)
    const block = match ? draft.pages[Number(match[1])]?.blocks[Number(match[2])] : null
    return { ...item, blockId: block?.id ?? null, field: match?.[3] ?? '' }
  })
}

/** Загрузить картинку или документ для сайта. Возвращает значение поля: { file_id, url, name, alt }. */
export async function uploadAsset(blob, name, purpose = 'image') {
  const body = new FormData()
  body.append('file', blob, name)
  body.append('purpose', purpose)
  const file = (await http.post('/v1/files', body, { headers: { 'Content-Type': 'multipart/form-data' } })).data
  return { file_id: file.id, url: file.url, name: file.name, alt: '' }
}
