<script setup>
import QRCode from 'qrcode'
import { computed, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import {
  AGGREGATE_LABELS,
  RANK_LABELS,
  SHEET_MODE_LABELS,
  SHEET_STATUS_LABELS,
  SHEET_STATUS_TONES,
  addWorks,
  anonymousUrl,
  deleteSheet,
  distribute,
  fetchSheet,
  formatJudges,
  parseJudges,
  setJudgeAccess,
  formatPoints,
  removeWork,
  setJudges,
  setSheetStatus,
  updateSheet,
} from '@/api/evaluation'
import { fetchEvent } from '@/api/events'
import { errorMessage } from '@/api/http'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import SkeletonPage from '@/components/skeleton/SkeletonPage.vue'

const props = defineProps({ id: { type: String, required: true }, sheetId: { type: String, required: true } })
const router = useRouter()

const sheet = ref(null)
const event = ref(null)
const error = ref('')
const notice = ref('')
const judgesText = ref('')
const confirmForce = ref(false)
const directionIds = ref([])
const perWork = ref(3)
const qr = ref(null) // { title, url, image }
const sortBy = ref('rank')

const canPublic = computed(() => sheet.value?.mode !== 'jury')
const canManage = computed(() => !!event.value?.can_manage)
const isStaff = computed(() => canManage.value || !!event.value?.my_roles.includes('moderator'))
const works = computed(() => {
  const list = [...(sheet.value?.works ?? [])]
  if (sortBy.value === 'rank') list.sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9) || a.number - b.number)
  else list.sort((a, b) => a.number - b.number)
  return list
})
const progress = computed(() => {
  const total = sheet.value?.judges.reduce((sum, j) => sum + j.total, 0) ?? 0
  const scored = sheet.value?.judges.reduce((sum, j) => sum + j.scored, 0) ?? 0
  return { total, scored, percent: total ? Math.round((100 * scored) / total) : 0 }
})

async function load() {
  error.value = ''
  try {
    ;[sheet.value, event.value] = await Promise.all([fetchSheet(props.sheetId), fetchEvent(props.id)])
    judgesText.value = formatJudges(sheet.value.judges)
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function run(fn, message = '') {
  error.value = ''
  notice.value = ''
  try {
    const result = await fn()
    if (result?.works) sheet.value = result
    else await load()
    notice.value = typeof message === 'function' ? message(result) : message
    return true
  } catch (e) {
    error.value = errorMessage(e)
    return false
  }
}

async function saveJudges(force = false) {
  const ok = await run(() => setJudges(sheet.value.id, parseJudges(judgesText.value), force), 'Список судей сохранён')
  confirmForce.value = !ok && error.value.includes('Подтвердите')
}

async function showQr(work) {
  const url = anonymousUrl(work.public_token)
  qr.value = { title: `№${work.number} · ${work.title}`, url, image: await QRCode.toDataURL(url, { width: 320, margin: 1 }) }
}

async function remove() {
  if (await run(() => deleteSheet(sheet.value.id))) await router.push({ name: 'event', params: { id: props.id }, query: { tab: 'evaluation' } })
}

watch(() => props.sheetId, load, { immediate: true })
</script>

<template>
  <p v-if="!sheet && error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
  <SkeletonPage v-else-if="!sheet" :cards="3" />

  <div v-else class="grid gap-6">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <RouterLink :to="{ name: 'event', params: { id }, query: { tab: 'evaluation' } }" class="text-sm text-ink-muted hover:text-ink">← {{ event?.title }}</RouterLink>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <h1 class="text-2xl font-bold">{{ sheet.title }}</h1>
          <UiBadge :tone="SHEET_STATUS_TONES[sheet.status]">{{ SHEET_STATUS_LABELS[sheet.status] }}</UiBadge>
        </div>
        <p class="mt-1 text-sm text-ink-muted">{{ sheet.scorecard_title }} · {{ SHEET_MODE_LABELS[sheet.mode] }} · оценено {{ progress.scored }} из {{ progress.total }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <UiButton v-if="isStaff && sheet.status !== 'active'" variant="primary" @click="run(() => setSheetStatus(sheet.id, 'active'), 'Оценка запущена')">
          {{ sheet.status === 'closed' ? 'Открыть снова' : 'Запустить оценку' }}
        </UiButton>
        <UiButton v-if="isStaff && sheet.status === 'active'" @click="run(() => setSheetStatus(sheet.id, 'closed'), 'Лист закрыт')">Закрыть лист</UiButton>
        <RouterLink
          v-if="isStaff && sheet.judges.length"
          :to="{ name: 'judge-cards', params: { id, sheetId } }"
          class="inline-flex h-10 items-center rounded-control border border-line bg-surface px-4 font-medium hover:bg-brand-50"
        >
          Листы судей с QR
        </RouterLink>
        <UiButton v-if="canManage && sheet.status === 'draft'" variant="ghost" @click="remove">Удалить</UiButton>
      </div>
    </div>

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <p v-if="notice" role="status" class="rounded-control bg-green-100 px-4 py-3 text-green-800">{{ notice }}</p>

    <div class="grid gap-6 lg:grid-cols-2">
      <UiCard v-if="canManage">
        <template #title>Работы</template>
        <p class="text-sm text-ink-muted">Добавляются принятые заявки. Повторно добавить уже включённые работы нельзя.</p>
        <div v-if="event?.directions.length" class="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm">
          <label v-for="d in event.directions" :key="d.id" class="flex items-center gap-2">
            <input v-model="directionIds" type="checkbox" :value="d.id" class="size-4 accent-brand-600" /> {{ d.title }}
          </label>
        </div>
        <UiButton
          v-if="sheet.stage_id"
          class="mt-3 mr-2"
          size="sm"
          variant="primary"
          @click="run(() => addWorks(sheet.id, { source: 'stage', direction_ids: directionIds.length ? directionIds : null }), 'Добавлены участники этапа')"
        >
          Добавить участников этапа
        </UiButton>
        <UiButton class="mt-3" size="sm" @click="run(() => addWorks(sheet.id, { direction_ids: directionIds.length ? directionIds : null }), 'Работы добавлены')">
          Добавить принятые заявки{{ directionIds.length ? ' выбранных направлений' : '' }}
        </UiButton>
      </UiCard>

      <UiCard>
        <template #title>Судьи</template>
        <template v-if="canManage">
          <label class="grid gap-1.5 text-sm">
            <span class="text-ink-muted">По одному в строке: «Фамилия Имя Отчество, email». Без email судья входит только по QR с листа судьи.</span>
            <textarea v-model="judgesText" rows="5" placeholder="Петров Иван Сергеевич, petrov@example.ru&#10;Сидорова Мария Петровна" class="rounded-control border border-line bg-surface px-3 py-2" />
          </label>
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <UiButton size="sm" @click="saveJudges(false)">Сохранить судей</UiButton>
            <UiButton v-if="confirmForce" size="sm" variant="danger" @click="saveJudges(true)">Удалить вместе с оценками</UiButton>
          </div>
          <div class="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4 text-sm">
            <span>Распределить работы:</span>
            <UiButton size="sm" @click="run(() => distribute(sheet.id, 'all', 1), (r) => `Назначено оценок: ${r.created}. Конфликт интересов: ${r.conflicts}.`)">Каждому судье все</UiButton>
            <span>или по</span>
            <input v-model.number="perWork" type="number" min="1" aria-label="Судей на работу" class="h-8 w-16 rounded-control border border-line bg-surface px-2" />
            <UiButton size="sm" @click="run(() => distribute(sheet.id, 'per_work', perWork), (r) => `Назначено оценок: ${r.created}. Конфликт интересов: ${r.conflicts}.`)">судьи на работу</UiButton>
          </div>
        </template>
        <p v-if="sheet.status === 'closed'" class="mt-4 text-sm text-ink-muted">Лист закрыт. Судье, который не успел, можно открыть оценку отдельно.</p>
        <ul v-if="sheet.judges.length" class="mt-4 grid gap-2 text-sm">
          <li v-for="judge in sheet.judges" :key="judge.user_id" class="flex flex-wrap items-center gap-3">
            <span class="min-w-0 flex-1 truncate">
              {{ judge.full_name }}<span v-if="!judge.email" class="text-ink-muted"> · вход по QR</span>
            </span>
            <span class="tabular-nums" :class="judge.total && judge.scored === judge.total ? 'text-green-700' : 'text-ink-muted'">{{ judge.scored }} / {{ judge.total }}</span>
            <RouterLink
              v-if="isStaff"
              :to="{ name: 'judge-cards', params: { id, sheetId }, query: { user: judge.user_id } }"
              class="text-brand-700 hover:underline"
            >
              QR
            </RouterLink>
            <UiButton
              v-if="isStaff && sheet.status === 'closed'"
              size="sm"
              :variant="judge.reopened ? 'secondary' : 'ghost'"
              @click="run(() => setJudgeAccess(sheet.id, judge.user_id, !judge.reopened), judge.reopened ? 'Оценка для судьи закрыта' : 'Судья может продолжить оценку')"
            >
              {{ judge.reopened ? 'Закрыть доступ' : 'Открыть доступ' }}
            </UiButton>
          </li>
        </ul>
      </UiCard>
    </div>

    <UiCard v-if="canManage">
      <template #title>Настройки подсчёта</template>
      <div class="flex flex-wrap gap-4 text-sm">
        <label class="flex items-center gap-2">
          Кто оценивает
          <select :value="sheet.mode" class="h-9 rounded-control border border-line bg-surface px-2" @change="run(() => updateSheet(sheet.id, { mode: $event.target.value }))">
            <option v-for="(label, value) in SHEET_MODE_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <label class="flex items-center gap-2">
          Итог по оценкам
          <select :value="sheet.aggregate" class="h-9 rounded-control border border-line bg-surface px-2" @change="run(() => updateSheet(sheet.id, { aggregate: $event.target.value }))">
            <option v-for="(label, value) in AGGREGATE_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <label class="flex items-center gap-2">
          Места при равенстве
          <select :value="sheet.rank_method" class="h-9 rounded-control border border-line bg-surface px-2" @change="run(() => updateSheet(sheet.id, { rank_method: $event.target.value }))">
            <option v-for="(label, value) in RANK_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <label v-if="sheet.mode === 'mixed'" class="flex items-center gap-2">
          <input type="checkbox" :checked="sheet.include_anonymous" class="size-4 accent-brand-600" @change="run(() => updateSheet(sheet.id, { include_anonymous: $event.target.checked }))" />
          Учитывать оценки зрителей в итоге
        </label>
      </div>
    </UiCard>

    <div v-if="qr" class="rounded-card border border-brand-200 bg-surface p-5 text-center">
      <p class="font-semibold">{{ qr.title }}</p>
      <img :src="qr.image" alt="QR-код для оценки работы" class="mx-auto my-3 size-64" />
      <p class="break-all text-sm text-ink-muted">{{ qr.url }}</p>
      <UiButton class="mt-3" size="sm" variant="ghost" @click="qr = null">Закрыть</UiButton>
    </div>

    <div class="overflow-x-auto rounded-card border border-line bg-surface">
      <div class="flex items-center justify-between gap-3 px-4 py-3">
        <h2 class="font-semibold">Результаты</h2>
        <select v-model="sortBy" aria-label="Сортировка" class="h-9 rounded-control border border-line bg-surface px-2 text-sm">
          <option value="rank">По месту</option>
          <option value="number">По номеру заявки</option>
        </select>
      </div>
      <table class="w-full text-sm">
        <thead class="bg-canvas text-left text-xs text-ink-muted">
          <tr>
            <th class="px-3 py-2">Место</th>
            <th class="px-3 py-2">№</th>
            <th class="px-3 py-2">Работа</th>
            <th class="px-3 py-2 text-right">Балл</th>
            <th class="px-3 py-2">Оценки жюри</th>
            <th v-if="canPublic" class="px-3 py-2">Зрители</th>
            <th class="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="work in works" :key="work.id" class="border-t border-line">
            <td class="px-3 py-2 font-semibold tabular-nums">{{ work.rank ?? '—' }}</td>
            <td class="px-3 py-2 tabular-nums text-ink-muted">{{ work.number }}</td>
            <td class="px-3 py-2">
              <p class="font-medium">{{ work.title || 'Без названия' }}</p>
              <p class="text-xs text-ink-muted">{{ work.participants.join(', ') }}<span v-if="work.direction"> · {{ work.direction }}</span></p>
            </td>
            <td class="px-3 py-2 text-right font-semibold tabular-nums text-score-600">{{ formatPoints(work.score) }}</td>
            <td class="px-3 py-2 tabular-nums" :class="work.is_scored ? 'text-green-700' : 'text-ink-muted'">{{ work.evaluations_scored }} / {{ work.evaluations_total }}</td>
            <td v-if="canPublic" class="px-3 py-2 tabular-nums">{{ work.anonymous_count }}</td>
            <td class="px-3 py-2 whitespace-nowrap text-right">
              <UiButton v-if="canPublic" size="sm" variant="ghost" @click="showQr(work)">QR</UiButton>
              <UiButton v-if="canManage && !work.evaluations_scored && !work.anonymous_count" size="sm" variant="ghost" @click="run(() => removeWork(sheet.id, work.id))">Убрать</UiButton>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!works.length" class="px-4 py-8 text-center text-ink-muted">В листе пока нет работ.</p>
    </div>
  </div>
</template>
