<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  APP_STATUS_LABELS,
  APP_STATUS_TONES,
  createStaffApplication,
  decideMany,
  exportUrl,
  fetchEventApplications,
  fetchForm,
} from '@/api/applications'
import { errorMessage } from '@/api/http'
import ApplicationReview from '@/components/events/ApplicationReview.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import SkeletonTable from '@/components/skeleton/SkeletonTable.vue'

const props = defineProps({ event: { type: Object, required: true } })

const PAGE = 50
const page = ref({ items: [], total: 0, counts: {} })
const fields = ref([])
const status = ref('submitted')
const directionId = ref('')
const search = ref('')
const offset = ref(0)
const loading = ref(false)
const error = ref('')
const selected = ref([])
const openedId = ref(null)
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

const statuses = ['submitted', 'needs_changes', 'accepted', 'rejected', 'withdrawn']
const total = computed(() => Object.values(page.value.counts).reduce((sum, n) => sum + n, 0))
const allSelected = computed(() => page.value.items.length > 0 && selected.value.length === page.value.items.length)

async function load() {
  loading.value = true
  error.value = ''
  try {
    page.value = await fetchEventApplications(props.event.id, {
      status: status.value,
      direction_id: directionId.value || undefined,
      search: search.value,
      offset: offset.value,
      limit: PAGE,
    })
    selected.value = selected.value.filter((id) => page.value.items.some((a) => a.id === id))
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
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

function formatDate(value) {
  return value ? new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '—'
}

let timer
watch(search, () => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    offset.value = 0
    load()
  }, 300)
})
watch([status, directionId], () => {
  offset.value = 0
  openedId.value = null
  load()
})
watch(offset, load)

onMounted(async () => {
  load()
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
      <input v-model="search" type="search" placeholder="Название или участник" aria-label="Поиск заявок" class="h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 sm:max-w-xs" />
      <select v-if="event.directions.length" v-model="directionId" aria-label="Направление" class="h-10 rounded-control border border-line bg-surface px-3 text-sm">
        <option value="">Все направления</option>
        <option v-for="d in event.directions" :key="d.id" :value="d.id">{{ d.title }}</option>
      </select>
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
        <select v-model="fresh.status" class="h-10 rounded-control border border-line bg-surface px-3">
          <option value="accepted">Сразу принята</option>
          <option value="submitted">На рассмотрении</option>
        </select>
      </label>
      <div class="flex items-end"><UiButton type="submit" variant="primary">Создать и заполнить</UiButton></div>
      <p class="text-ink-muted sm:col-span-3">
        Для заявок, принятых на месте или по почте. Окно приёма заявок не учитывается, согласия на обработку данных собирает оргкомитет.
      </p>
    </form>

    <div v-if="selected.length" class="flex flex-wrap items-center gap-3 rounded-control border border-brand-200 bg-brand-50 p-3 text-sm">
      <span class="font-medium">Выбрано: {{ selected.length }}</span>
      <UiButton size="sm" variant="primary" @click="bulk('accepted')">Принять</UiButton>
      <input v-model="bulkComment" placeholder="Комментарий (нужен для отклонения)" aria-label="Комментарий" class="h-8 min-w-0 flex-1 rounded-control border border-line bg-surface px-2" />
      <UiButton size="sm" variant="danger" @click="bulk('rejected')">Отклонить</UiButton>
    </div>
    <p v-if="bulkResult" role="status" class="text-sm text-ink-muted">{{ bulkResult }}</p>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>

    <ApplicationReview v-if="openedId" :application-id="openedId" :fields="fields" @decided="load" @close="openedId = null" />

    <div class="overflow-x-auto rounded-card border border-line bg-surface" :aria-busy="loading">
      <SkeletonTable v-if="loading && !page.items.length" :rows="5" :columns="5" />
      <table class="w-full text-sm">
        <thead class="bg-canvas text-left text-xs text-ink-muted">
          <tr>
            <th class="w-10 px-3 py-2"><input type="checkbox" :checked="allSelected" aria-label="Выбрать все" class="size-4 accent-brand-600" @change="toggleAll($event.target.checked)" /></th>
            <th class="px-3 py-2">№</th>
            <th class="px-3 py-2">Работа</th>
            <th class="px-3 py-2">Участники</th>
            <th class="px-3 py-2">Руководитель</th>
            <th class="px-3 py-2">Отправлена</th>
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
            <td class="px-3 py-2" @click.stop><input v-model="selected" type="checkbox" :value="app.id" :aria-label="`Выбрать заявку ${app.number}`" class="size-4 accent-brand-600" /></td>
            <td class="px-3 py-2 tabular-nums">{{ app.number }}</td>
            <td class="px-3 py-2">
              <p class="font-medium">{{ app.title || 'Без названия' }}</p>
              <p v-if="app.direction" class="text-xs text-ink-muted">{{ app.direction }}</p>
            </td>
            <td class="px-3 py-2">{{ app.participants.join(', ') }}</td>
            <td class="px-3 py-2">{{ app.supervisors.join(', ') || '—' }}</td>
            <td class="px-3 py-2 whitespace-nowrap text-ink-muted">{{ formatDate(app.submitted_at) }}</td>
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
