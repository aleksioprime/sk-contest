import { useRoute, useRouter } from 'vue-router'

export function useUrlQuery() {
  const route = useRoute()
  const router = useRouter()

  function setQuery(values, { replace = false } = {}) {
    const query = { ...route.query, ...values }
    const location = { path: route.path, query, hash: route.hash }
    return replace ? router.replace(location) : router.push(location)
  }

  return { route, setQuery }
}
