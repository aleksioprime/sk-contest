import { computed, onBeforeUnmount, ref, watch } from 'vue'

export function useListPage(route, setQuery, pageSize, { pageQuery = 'page', resetQuery = {}, filters = [] } = {}) {
  const search = ref('')
  const searchTerm = ref('')
  const searchOffset = ref(0)
  let timer
  let active = true

  watch(search, (value) => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      searchOffset.value = 0
      searchTerm.value = value
    }, 300)
  })
  onBeforeUnmount(() => {
    active = false
    clearTimeout(timer)
  })
  watch(filters, () => { searchOffset.value = 0 })

  const offset = computed({
    get() {
      if (searchTerm.value) return searchOffset.value
      const value = route.query[pageQuery]
      if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value)) return 0
      const result = (Number(value) - 1) * pageSize
      return Number.isSafeInteger(result) ? result : 0
    },
    set(value) {
      if (searchTerm.value) searchOffset.value = value
      else goToOffset(value)
    },
  })

  function goToOffset(value, replace = false) {
    return setQuery({ ...resetQuery, [pageQuery]: value ? String(value / pageSize + 1) : undefined }, { replace })
  }

  function fitTotal(total) {
    if (!active) return
    const lastOffset = Math.floor(Math.max(0, total - 1) / pageSize) * pageSize
    if (offset.value <= lastOffset) return
    if (searchTerm.value) searchOffset.value = lastOffset
    else goToOffset(lastOffset, true)
  }

  return { search, searchTerm, offset, fitTotal }
}
