<script setup>
/** Вкладка «Заявки» мероприятия: список с фильтрами, массовые решения, создание заявки сотрудником и выгрузка. */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  APP_STATUS_LABELS,
  APP_STATUS_TONES,
  SOURCE_LABELS,
  createStaffApplication,
  decideMany,
  exportUrl,
  fetchEventApplications,
  fetchForm,
} from '@/api/applications'
import { errorMessage, SkeletonTable, UiBadge, UiButton, UiSelect } from 'sk-ui'
import ApplicationReview from '@/components/events/ApplicationReview.vue'
import { formatDateTime } from '@/utils/dates'
import { useListPage } from '@/utils/useListPage'
import { useUrlQuery } from '@/utils/useUrlQuery'

const props = defineProps({ event: { type: Object, required: true } })

const PAGE = 50
const page = ref({ items: [], total: 0, counts: {} })
const fields = ref([])
const loading = ref(false)
const error = ref('')
const selected = ref([])
const searchedApplication = ref(null)
const reviewedApplication = ref(null)
const bulkComment = ref('')
const bulkResult = ref('')

const router = useRouter()
const creating = ref(false)
const fresh = ref({ owner_email: '', status: 'accepted' })

async function createApplication() {
  error.value = ''
  try {
    const app = await createStaffApplication(props.event.id, {
      owner_email: fresh.value.owner_email.trim() || null,
      status: fresh.value.status,
    })
    await router.push({ name: 'application', params: { id: app.id }, query: { manage: '1' } })
  } catch (e) {
    error.value = errorMessage(e)
  }
}

const statuses = ['requested', 'draft', 'submitted', 'needs_changes', 'accepted', 'rejected', 'withdrawn']
const { route, setQuery } = useUrlQuery()
const resetList = { page: undefined, application: undefined }
const status = computed({
  get: () => {
    if (route.query.status === 'all') return ''
    return statuses.includes(route.query.status) ? route.query.status : 'requested'
  },
  set: (value) => {
    if (value !== status.value) setQuery({ ...resetList, status: value === 'requested' ? undefined : value || 'all' })
  },
})
const directionId = computed({
  get: () => props.event.directions.find((direction) => String(direction.id) === route.query.direction)?.id ?? '',
  set: (value) => {
    if (value !== directionId.value) setQuery({ ...resetList, direction: value ? String(value) : undefined })
  },
})
const { search, searchTerm, offset, fitTotal } = useListPage(route, setQuery, PAGE, {
  resetQuery: { application: undefined },
  filters: [status, directionId],
})
const openedId = computed({
  get: () => {
    const value = searchTerm.value ? searchedApplication.value : route.query.application
    return page.value.items.find((application) => String(application.id) === value)?.id
      ?? (String(reviewedApplication.value) === value ? reviewedApplication.value : null)
  },
  set: (value) => {
    if (searchTerm.value) searchedApplication.value = value == null ? null : String(value)
    else setQuery({ application: value == null ? undefined : String(value) })
  },
})
const total = computed(() => Object.values(page.value.counts).reduce((sum, n) => sum + n, 0))
const archived = computed(() => props.event.status === 'archived')
const allSelected = computed(() => page.value.items.length > 0 && selected.value.length === page.value.items.length)

let lastLoad = 0
async function load() {
  const request = ++lastLoad
  loading.value = true
  error.value = ''
  try {
    const result = await fetchEventApplications(props.event.id, {
      status: status.value,
      direction_id: directionId.value || undefined,
      search: searchTerm.value,
      offset: offset.value,
      limit: PAGE,
    })
    if (request !== lastLoad) return
    page.value = result
    fitTotal(result.total)
    selected.value = selected.value.filter((id) => result.items.some((a) => a.id === id))
  } catch (e) {
    if (request === lastLoad) error.value = errorMessage(e)
  } finally {
    if (request === lastLoad) loading.value = false
  }
}

function refreshReview() {
  reviewedApplication.value = openedId.value
  return load()
}

function toggleAll(checked) {
  selected.value = checked ? page.value.items.map((a) => a.id) : []
}

async function bulk(newStatus) {
  bulkResult.value = ''
  error.value = ''
  try {
    const result = await decideMany(props.event.id, selected.value, newStatus, bulkComment.value)
    bulkResult.value = `Обновлено заявок: ${result.updated}` + (result.skipped.length ? `. Пропущены №${result.skipped.join(', №')}: их нельзя перевести в этот статус.` : '')
    selected.value = []
    bulkComment.value = ''
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

watch(() => route.query.application, () => { reviewedApplication.value = null })
watch([() => props.event.id, status, directionId, offset, searchTerm], () => {
  reviewedApplication.value = null
  searchedApplication.value = null
  page.value = { ...page.value, items: [] }
  selected.value = []
  load()
}, { immediate: true })

onMounted(async () => {
  try {
    fields.value = (await fetchForm(props.event.id)).fields
  } catch {
    fields.value = []
  }
})
</script>

<template>
  <div class="grid gap-4">
    <div class="flex flex-wrap items-center gap-2">
      <button
        v-for="item in ['', ...statuses]"
        :key="item || 'all'"
        type="button"
        class="rounded-full border px-3 py-1 text-sm"
        :class="status === item ? 'border-brand-500 bg-brand-100 text-brand-700' : 'border-line bg-surface text-ink-muted hover:text-ink'"
        :aria-pressed="status === item"
        @click="status = item"
      >
        {{ item ? APP_STATUS_LABELS[item] : 'Все' }} <span class="tabular-nums">{{ item ? page.counts[item] ?? 0 : total }}</span>
      </button>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <input v-model="search" type="search" placeholder="Название, участник или email" aria-label="Поиск заявок" class="h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 sm:max-w-xs" />
      <UiSelect v-if="event.directions.length" v-model="directionId" aria-label="Направление" class="text-sm">
        <option value="">Все направления</option>
        <option v-for="d in event.directions" :key="d.id" :value="d.id">{{ d.title }}</option>
      </UiSelect>
      <div class="ml-auto flex gap-2 text-sm">
        <UiButton variant="primary" @click="creating = !creating">Добавить заявку</UiButton>
        <a :href="exportUrl(event.id)" class="rounded-control border border-line bg-surface px-3 py-2 hover:bg-brand-50">Выгрузить все</a>
        <a :href="exportUrl(event.id, true)" class="rounded-control border border-line bg-surface px-3 py-2 hover:bg-brand-50">Только принятые</a>
      </div>
    </div>

    <form v-if="creating" class="grid gap-3 rounded-card border border-line bg-surface p-4 text-sm sm:grid-cols-[2fr_1fr_auto]" @submit.prevent="createApplication">
      <label class="grid gap-1">
        <span class="font-medium">Email контактного лица <span class="font-normal text-ink-muted">(необязательно)</span></span>
        <input v-model="fresh.owner_email" type="email" placeholder="Увидит заявку в своём кабинете" class="h-10 rounded-control border border-line bg-surface px-3" />
      </label>
      <label class="grid gap-1">
        <span class="font-medium">Статус</span>
        <UiSelect v-model="fresh.status">
          <option value="accepted">Сразу принята</option>
          <option value="submitted">На рассмотрении</option>
        </UiSelect>
      </label>
      <div class="flex items-end"><UiButton type="submit" variant="primary">Создать и заполнить</UiButton></div>
      <p class="text-ink-muted sm:col-span-3">
        Для заявок, принятых на месте или по почте. Окно приёма заявок не учитывается, согласия на обработку данных собирает оргкомитет.
      </p>
    </form>

    <div v-if="selected.length && !archived" class="flex flex-wrap items-center gap-3 rounded-control border border-brand-200 bg-brand-50 p-3 text-sm">
      <span class="font-medium">Выбрано: {{ selected.length }}</span>
      <UiButton v-if="status === 'requested'" size="sm" variant="primary" @click="bulk('confirmed')">Подтвердить и пригласить</UiButton>
      <UiButton v-else size="sm" variant="primary" @click="bulk('accepted')">Принять</UiButton>
      <input v-model="bulkComment" placeholder="Комментарий (нужен для отклонения)" aria-label="Комментарий" class="h-8 min-w-0 flex-1 rounded-control border border-line bg-surface px-2" />
      <UiButton size="sm" variant="danger" @click="bulk('rejected')">Отклонить</UiButton>
    </div>
    <p v-if="bulkResult" role="status" class="text-sm text-ink-muted">{{ bulkResult }}</p>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>

    <ApplicationReview v-if="openedId" :key="openedId" :application-id="openedId" :event-id="event.id" :fields="fields" @decided="refreshReview" @close="openedId = null" />

    <div class="overflow-x-auto rounded-card border border-line bg-surface" :aria-busy="loading">
      <SkeletonTable v-if="loading && !page.items.length" :rows="5" :columns="5" />
      <table class="w-full text-sm">
        <thead class="bg-canvas text-left text-xs text-ink-muted">
          <tr>
            <th v-if="!archived" class="w-10 px-3 py-2"><input type="checkbox" :checked="allSelected" aria-label="Выбрать все" class="size-4 accent-brand-600" @change="toggleAll($event.target.checked)" /></th>
            <th class="px-3 py-2">№</th>
            <th class="px-3 py-2">Работа</th>
            <th class="px-3 py-2">Заявитель и участники</th>
            <th class="px-3 py-2">Руководитель</th>
            <th class="px-3 py-2">Поступила</th>
            <th class="px-3 py-2">Статус</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="app in page.items"
            :key="app.id"
            class="cursor-pointer border-t border-line hover:bg-brand-50"
            :class="{ 'bg-brand-50': openedId === app.id }"
            @click="openedId = app.id"
          >
            <td v-if="!archived" class="px-3 py-2" @click.stop><input v-model="selected" type="checkbox" :value="app.id" :aria-label="`Выбрать заявку ${app.number}`" class="size-4 accent-brand-600" /></td>
            <td class="px-3 py-2 tabular-nums">{{ app.number }}</td>
            <td class="px-3 py-2">
              <p class="font-medium">{{ app.title || 'Без названия' }}</p>
              <p v-if="app.direction" class="text-xs text-ink-muted">{{ app.direction }}</p>
            </td>
            <td class="px-3 py-2">
              <p>{{ app.participants.join(', ') || app.applicant_name }}</p>
              <p class="text-xs text-ink-muted">{{ [app.applicant_email, app.is_linked || app.source === 'import' ? '' : 'без учётной записи'].filter(Boolean).join(' · ') }}</p>
            </td>
            <td class="px-3 py-2">{{ app.supervisors.join(', ') || '—' }}</td>
            <td class="px-3 py-2 whitespace-nowrap text-ink-muted">
              <p>{{ formatDateTime(app.submitted_at ?? app.created_at) }}</p>
              <p class="text-xs">{{ SOURCE_LABELS[app.source] }}</p>
            </td>
            <td class="px-3 py-2"><UiBadge :tone="APP_STATUS_TONES[app.status]">{{ APP_STATUS_LABELS[app.status] }}</UiBadge></td>
          </tr>
        </tbody>
      </table>
      <p v-if="!loading && !page.items.length" class="px-4 py-8 text-center text-ink-muted">
        {{ search || directionId ? 'Ничего не нашли. Измените фильтры.' : 'Заявок в этом статусе нет.' }}
      </p>
    </div>

    <div v-if="page.total > PAGE" class="flex items-center gap-3 text-sm">
      <UiButton size="sm" :disabled="offset === 0" @click="offset = Math.max(0, offset - PAGE)">Назад</UiButton>
      <span>{{ offset + 1 }}–{{ Math.min(offset + PAGE, page.total) }} из {{ page.total }}</span>
      <UiButton size="sm" :disabled="offset + PAGE >= page.total" @click="offset += PAGE">Дальше</UiButton>
    </div>
  </div>
</template>
