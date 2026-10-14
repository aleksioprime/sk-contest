import { http } from './http'

export async function fetchPersons(params) {
  const { data } = await http.get('/v1/people/persons', { params })
  return data
}

export async function fetchUsers(params) {
  const { data } = await http.get('/v1/people/users', { params })
  return data
}

export async function updateUser(id, changes) {
  const { data } = await http.patch(`/v1/people/users/${id}`, changes)
  return data
}

export async function fetchSyncRuns() {
  const { data } = await http.get('/v1/people/sync')
  return data
}

export async function startSync(mode) {
  const { data } = await http.post('/v1/people/sync', { mode })
  return data
}

export async function createUser(payload) {
  const { data } = await http.post('/v1/people/users', payload)
  return data
}
