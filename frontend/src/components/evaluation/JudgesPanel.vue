<script setup>
/** Судьи листа: таблица, поиск по базе пользователей, новый судья с паролем. */
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { deadlinePassed, distribute, judgesPayload, searchUsers, setJudgeAccess, setJudges } from '@/api/evaluation'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({
  sheet: { type: Object, required: true },
  eventId: { type: [String, Number], required: true },
  canManage: { type: Boolean, default: false },
  isStaff: { type: Boolean, default: false },
  run: { type: Function, required: true }, // (fn, message) => Promise<boolean>, общий обработчик SheetView
})

const query = ref('')
const found = ref([])
const searching = ref(false)
const showNew = ref(false)
const fresh = ref({ full_name: '', email: '', password: '' })
const removing = ref(null)
const perWork = ref(3)
let timer

watch(query, (q) => {
  clearTimeout(timer)
  if (q.trim().length < 2) {
    found.value = []
    return
  }
  timer = setTimeout(async () => {
    searching.value = true
    try {
      const present = new Set(props.sheet.judges.map((j) => j.user_id))
      found.value = (await searchUsers(props.eventId, q)).filter((u) => !present.has(u.id))
    } finally {
      searching.value = false
    }
  }, 250)
})

const current = () => props.sheet.judges.map((j) => ({ user_id: j.user_id }))

async function addExisting(user) {
  query.value = ''
  found.value = []
  await props.run(() => setJudges(props.sheet.id, [...current(), { user_id: user.id }]), `Судья ${user.full_name || user.email} добавлен`)
}

async function addNew() {
  const judge = {
    full_name: fresh.value.full_name.trim(),
    email: fresh.value.email.trim() || null,
    password: fresh.value.password || null,
  }
  const ok = await props.run(() => setJudges(props.sheet.id, judgesPayload([...current(), judge])), 'Судья создан и добавлен в лист')
  if (ok) {
    fresh.value = { full_name: '', email: '', password: '' }
    showNew.value = false
  }
}

async function remove(judge, force = false) {
  const rest = current().filter((j) => j.user_id !== judge.user_id)
  const ok = await props.run(() => setJudges(props.sheet.id, rest, force), 'Судья убран из листа')
  removing.value = ok ? null : judge.user_id
}

const closedForJudges = () => props.sheet.status === 'closed' || deadlinePassed(props.sheet.deadline)
</script>

<template>
  <div class="grid gap-4">
    <div class="overflow-x-auto rounded-control border border-line">
      <table class="w-full text-sm">
        <thead class="bg-canvas text-left text-xs text-ink-muted">
          <tr>
            <th class="px-3 py-2">Судья</th>
            <th class="px-3 py-2">Вход</th>
            <th class="px-3 py-2 text-right">Оценено</th>
            <th class="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="judge in sheet.judges" :key="judge.user_id" class="border-t border-line align-top">
            <td class="px-3 py-2">
              <p class="font-medium">{{ judge.full_name }}</p>
              <p class="text-xs text-ink-muted">{{ judge.email || 'без email' }}</p>
            </td>
            <td class="px-3 py-2">
              <div class="flex flex-wrap gap-1">
                <UiBadge v-if="judge.has_password" tone="success">пароль</UiBadge>
                <UiBadge v-if="judge.email" tone="brand">почта</UiBadge>
                <UiBadge>QR</UiBadge>
              </div>
            </td>
            <td class="px-3 py-2 text-right tabular-nums" :class="judge.total && judge.scored === judge.total ? 'text-green-700' : 'text-ink-muted'">
              {{ judge.scored }} / {{ judge.total }}
            </td>
            <td class="px-3 py-2">
              <div class="flex flex-wrap justify-end gap-1">
                <RouterLink
                  v-if="isStaff"
                  :to="{ name: 'judge-cards', params: { id: eventId, sheetId: sheet.id }, query: { user: judge.user_id } }"
                  class="inline-flex h-8 items-center rounded-control px-2 text-brand-700 hover:bg-brand-50"
                >
                  Лист с QR
                </RouterLink>
                <UiButton
                  v-if="isStaff && closedForJudges()"
                  size="sm"
                  :variant="judge.reopened ? 'secondary' : 'ghost'"
                  @click="run(() => setJudgeAccess(sheet.id, judge.user_id, !judge.reopened), judge.reopened ? 'Оценка для судьи закрыта' : 'Судья может продолжить оценку')"
                >
                  {{ judge.reopened ? 'Закрыть доступ' : 'Открыть доступ' }}
                </UiButton>
                <template v-if="canManage">
                  <UiButton v-if="removing !== judge.user_id" size="sm" variant="ghost" @click="remove(judge)">Убрать</UiButton>
                  <UiButton v-else size="sm" variant="danger" @click="remove(judge, true)">Убрать с оценками</UiButton>
                </template>
              </div>
            </td>
          </tr>
          <tr v-if="!sheet.judges.length">
            <td colspan="4" class="px-3 py-6 text-center text-ink-muted">Судей пока нет</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="canManage" class="grid gap-3">
      <div class="relative">
        <input
          v-model="query"
          type="search"
          placeholder="Найти в базе: фамилия или email"
          aria-label="Найти судью в базе"
          class="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm"
        />
        <ul v-if="found.length || (searching && query)" class="absolute inset-x-0 top-11 z-10 max-h-64 overflow-y-auto rounded-control border border-line bg-surface shadow-lg">
          <li v-if="searching && !found.length" class="px-3 py-2 text-sm text-ink-muted">Ищем…</li>
          <li v-for="user in found" :key="user.id">
            <button type="button" class="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-brand-50" @click="addExisting(user)">
              <span class="min-w-0 flex-1 truncate">{{ user.full_name || user.email }}</span>
              <span class="truncate text-xs text-ink-muted">{{ user.email || 'вход по QR' }}</span>
            </button>
          </li>
        </ul>
        <p v-if="query.trim().length >= 2 && !searching && !found.length" class="mt-1 text-sm text-ink-muted">
          В базе не нашли.
          <button type="button" class="text-brand-700 hover:underline" @click="(showNew = true), (fresh.full_name = query.trim())">Создать нового судью</button>
        </p>
      </div>

      <button v-if="!showNew" type="button" class="justify-self-start text-sm text-brand-700 hover:underline" @click="showNew = true">
        + Новый судья
      </button>
      <form v-else class="grid gap-3 rounded-control border border-line p-3 text-sm sm:grid-cols-3" @submit.prevent="addNew">
        <label class="grid gap-1"><span class="font-medium">ФИО</span><input v-model="fresh.full_name" required class="h-9 rounded-control border border-line bg-surface px-2" /></label>
        <label class="grid gap-1"><span class="font-medium">Email <span class="font-normal text-ink-muted">(для входа по паролю)</span></span><input v-model="fresh.email" type="email" class="h-9 rounded-control border border-line bg-surface px-2" /></label>
        <label class="grid gap-1">
          <span class="font-medium">Пароль <span class="font-normal text-ink-muted">(от 8 символов)</span></span>
          <input v-model="fresh.password" minlength="8" autocomplete="off" class="h-9 rounded-control border border-line bg-surface px-2" />
        </label>
        <p class="text-ink-muted sm:col-span-3">
          Судья войдёт по email и паролю или по QR с распечатанного листа — сразу в этот оценочный лист.
          В следующий раз его можно будет найти в базе.
        </p>
        <div class="flex gap-2 sm:col-span-3">
          <UiButton type="submit" size="sm" variant="primary">Добавить</UiButton>
          <UiButton size="sm" variant="ghost" @click="showNew = false">Отмена</UiButton>
        </div>
      </form>

      <div class="flex flex-wrap items-center gap-2 border-t border-line pt-4 text-sm">
        <span>Распределить работы:</span>
        <UiButton size="sm" @click="run(() => distribute(sheet.id, 'all', 1), (r) => `Назначено оценок: ${r.created}. Конфликт интересов: ${r.conflicts}.`)">Каждому судье все</UiButton>
        <span>или по</span>
        <input v-model.number="perWork" type="number" min="1" aria-label="Судей на работу" class="h-8 w-16 rounded-control border border-line bg-surface px-2" />
        <UiButton size="sm" @click="run(() => distribute(sheet.id, 'per_work', perWork), (r) => `Назначено оценок: ${r.created}. Конфликт интересов: ${r.conflicts}.`)">судьи на работу</UiButton>
      </div>
    </div>
  </div>
</template>
