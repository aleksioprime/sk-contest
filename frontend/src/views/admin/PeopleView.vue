<script setup>
import { onMounted, ref, watch } from 'vue'
import { errorMessage } from '@/api/http'
import { fetchPersons, fetchSyncRuns, fetchUsers, startSync, updateUser } from '@/api/people'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import { useAuthStore } from '@/stores/auth'
import SkeletonTable from '@/components/skeleton/SkeletonTable.vue'

const auth = useAuthStore()
const PAGE = 50

const tab = ref('persons')
const search = ref('')
const kind = ref('')
const offset = ref(0)
const page = ref({ items: [], total: 0 })
const loading = ref(false)
const error = ref('')

const syncRuns = ref([])
const syncError = ref('')
const syncing = ref(false)

const kinds = [
  { value: '', label: 'Все' },
  { value: 'student', label: 'Ученики' },
  { value: 'employee', label: 'Сотрудники' },
  { value: 'external', label: 'Внешние' },
]
const syncStatus = {
  running: ['warning', 'идёт'],
  success: ['success', 'завершена'],
  failed: ['danger', 'ошибка'],
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { search: search.value, offset: offset.value, limit: PAGE }
    page.value = tab.value === 'persons' ? await fetchPersons({ ...params, kind: kind.value }) : await fetchUsers(params)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

async function loadSync() {
  try {
    syncRuns.value = await fetchSyncRuns()
  } catch {
    syncRuns.value = []
  }
}

let timer
watch(search, () => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    offset.value = 0
    load()
  }, 300)
})
watch([tab, kind], () => {
  offset.value = 0
  load()
})
watch(offset, load)

async function runSync(mode) {
  syncing.value = true
  syncError.value = ''
  try {
    await startSync(mode)
    await loadSync()
  } catch (e) {
    syncError.value = errorMessage(e)
  } finally {
    syncing.value = false
  }
}

async function toggle(user, field) {
  error.value = ''
  try {
    Object.assign(user, await updateUser(user.id, { [field]: !user[field] }))
  } catch (e) {
    error.value = errorMessage(e)
  }
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '—'
}

onMounted(() => {
  load()
  loadSync()
})
</script>

<template>
  <div class="grid gap-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold">Люди</h1>
        <p class="mt-1 text-ink-muted">Ученики и сотрудники приходят из SkolStream, внешние участники регистрируются сами.</p>
      </div>
    </div>

    <UiCard>
      <template #title>Синхронизация со SkolStream</template>
      <div class="flex flex-wrap items-center gap-3">
        <UiButton :loading="syncing" @click="runSync('incremental')">Обновить изменения</UiButton>
        <UiButton variant="ghost" :disabled="syncing" @click="runSync('full')">Полная выгрузка</UiButton>
        <span class="text-sm text-ink-muted">Автоматически каждую ночь в 3:00</span>
      </div>
      <p v-if="syncError" role="alert" class="mt-3 text-sm text-red-700">{{ syncError }}</p>
      <ul v-if="syncRuns.length" class="mt-4 grid gap-2 text-sm">
        <li v-for="run in syncRuns.slice(0, 3)" :key="run.id" class="flex flex-wrap items-center gap-2">
          <UiBadge :tone="syncStatus[run.status]?.[0] ?? 'neutral'">{{ syncStatus[run.status]?.[1] ?? run.status }}</UiBadge>
          <span>{{ formatDate(run.started_at) }}</span>
          <span class="text-ink-muted">{{ run.mode === 'full' ? 'полная' : 'изменения' }}</span>
          <span v-if="run.status === 'success'" class="text-ink-muted">
            · людей {{ run.stats.persons ?? 0 }}, классов {{ run.stats.classes ?? 0 }}, отключено {{ run.stats.deactivated ?? 0 }}
          </span>
          <span v-if="run.error" class="text-red-700">· {{ run.error }}</span>
        </li>
      </ul>
    </UiCard>

    <div class="flex flex-wrap items-center gap-3">
      <div class="flex rounded-control border border-line bg-surface p-1 text-sm" role="tablist">
        <button
          v-for="item in [{ id: 'persons', label: 'Персоны' }, { id: 'users', label: 'Учётные записи' }]"
          :key="item.id"
          role="tab"
          type="button"
          :aria-selected="tab === item.id"
          class="rounded-[8px] px-3 py-1.5"
          :class="tab === item.id ? 'bg-brand-100 text-brand-700' : 'text-ink-muted hover:text-ink'"
          @click="tab = item.id"
        >
          {{ item.label }}
        </button>
      </div>
      <input
        v-model="search"
        type="search"
        placeholder="Фамилия или email"
        aria-label="Поиск"
        class="h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 sm:max-w-xs"
      />
      <select v-if="tab === 'persons'" v-model="kind" aria-label="Тип" class="h-10 rounded-control border border-line bg-surface px-3">
        <option v-for="item in kinds" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
      <span class="text-sm text-ink-muted">Найдено: {{ page.total }}</span>
    </div>

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>

    <div class="overflow-x-auto rounded-card border border-line bg-surface" :aria-busy="loading">
      <SkeletonTable v-if="loading && !page.items.length" :rows="6" :columns="4" />
      <table v-if="tab === 'persons'" class="w-full text-sm">
        <thead class="bg-canvas text-left text-xs text-ink-muted">
          <tr><th class="px-4 py-2">ФИО</th><th class="px-4 py-2">Тип</th><th class="px-4 py-2">Класс или подразделение</th><th class="px-4 py-2">Email</th></tr>
        </thead>
        <tbody>
          <tr v-for="person in page.items" :key="person.id" class="border-t border-line" :class="{ 'opacity-50': !person.is_active }">
            <td class="px-4 py-2 font-medium">{{ person.full_name || '—' }}</td>
            <td class="px-4 py-2">
              <div class="flex flex-wrap gap-1">
                <UiBadge v-if="person.is_student" tone="brand">ученик</UiBadge>
                <UiBadge v-if="person.is_employee" tone="success">сотрудник</UiBadge>
                <UiBadge v-if="person.is_external">внешний</UiBadge>
                <UiBadge v-if="!person.is_active" tone="danger">неактивен</UiBadge>
              </div>
            </td>
            <td class="px-4 py-2">{{ person.study_class?.name || person.departments.map((d) => d.name).join(', ') || person.organization || '—' }}</td>
            <td class="px-4 py-2 text-ink-muted">{{ person.email || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <table v-else class="w-full text-sm">
        <thead class="bg-canvas text-left text-xs text-ink-muted">
          <tr><th class="px-4 py-2">Email</th><th class="px-4 py-2">Персона</th><th class="px-4 py-2">Последний вход</th><th class="px-4 py-2">Администратор</th><th class="px-4 py-2">Доступ</th></tr>
        </thead>
        <tbody>
          <tr v-for="user in page.items" :key="user.id" class="border-t border-line">
            <td class="px-4 py-2 font-medium">{{ user.email }}</td>
            <td class="px-4 py-2">{{ user.person?.full_name || '—' }}</td>
            <td class="px-4 py-2 text-ink-muted">{{ formatDate(user.last_login_at) }}</td>
            <td class="px-4 py-2">
              <input
                type="checkbox"
                :checked="user.is_superuser"
                :disabled="user.id === auth.user?.id"
                :aria-label="`Администратор: ${user.email}`"
                @change="toggle(user, 'is_superuser')"
              />
            </td>
            <td class="px-4 py-2">
              <UiButton size="sm" variant="ghost" :disabled="user.id === auth.user?.id" @click="toggle(user, 'is_active')">
                {{ user.is_active ? 'Отключить' : 'Включить' }}
              </UiButton>
            </td>
          </tr>
        </tbody>
      </table>

      <p v-if="!loading && !page.items.length" class="px-4 py-8 text-center text-ink-muted">
        {{ search ? 'Никого не нашли. Измените запрос.' : 'Пока пусто. Запустите синхронизацию со SkolStream.' }}
      </p>
    </div>

    <div v-if="page.total > PAGE" class="flex items-center gap-3 text-sm">
      <UiButton size="sm" :disabled="offset === 0" @click="offset = Math.max(0, offset - PAGE)">Назад</UiButton>
      <span>{{ offset + 1 }}–{{ Math.min(offset + PAGE, page.total) }} из {{ page.total }}</span>
      <UiButton size="sm" :disabled="offset + PAGE >= page.total" @click="offset += PAGE">Дальше</UiButton>
    </div>
  </div>
</template>
