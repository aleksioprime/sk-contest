import { http } from 'sk-ui'

export async function fetchMeta() {
  const { data } = await http.get('/v1/meta')
  return data
}

export async function fetchReadiness() {
  const { data } = await http.get('/health/ready', { validateStatus: () => true })
  return data
}
