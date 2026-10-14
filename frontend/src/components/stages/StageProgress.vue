<script setup>
/** Ход по этапам: участники, баллы из листов, правило перехода, расписание защит. */
import { computed, reactive, ref, watch } from 'vue'
import { formatPoints } from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import {
  STAGE_STATUS_LABELS,
  STAGE_STATUS_TONES,
  addSlot,
  admitToStage,
  applyAdvance,
  deleteSlot,
  fetchStage,
  programUrl,
  setStageRule,
  updateParticipant,
} from '@/api/stages'
import SkeletonTable from '@/components/skeleton/SkeletonTable.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'

const props = defineProps({ event: { type: Object, required: true } })

const stages = computed(() => [...props.event.stages].sort((a, b) => a.order - b.order))
const stageId = ref(stages.value[0]?.id ?? null)
const data = ref(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const rule = reactive({ type: 'manual', n: 3, per_direction: true, threshold: null })
const decisions = ref({})
const slot = reactive({ title: '', room: '', starts_at: '', ends_at: '' })
const confirmApply = ref(false)

const manage = computed(() => props.event.can_manage)
const isFirst = computed(() => stages.value[0]?.id === stageId.value)
const pending = computed(() => Object.values(decisions.value).filter(Boolean).length)

function fill(overview) {
  data.value = overview
  Object.assign(rule, overview.rule)
  decisions.value = Object.fromEntries(overview.participants.filter((p) => p.status !== 'withdrawn').map((p) => [p.id, p.proposal]))
}

async function load() {
  if (!stageId.value) return
  loading.value = true
  error.value = ''
  try {
    fill(await fetchStage(props.event.id, stageId.value))
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

async function run(fn, message) {
  error.value = ''
  notice.value = ''
  try {
    const result = await fn()
    if (result?.participants) fill(result)
    else await load()
    notice.value = typeof message === 'function' ? message(result) : message
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function apply() {
  confirmApply.value = false
  const chosen = Object.fromEntries(Object.entries(decisions.value).filter(([, status]) => status))
  await run(() => applyAdvance(props.event.id, stageId.value, chosen), (r) =>
    `Прошли: ${r.passed}, не прошли: ${r.not_passed}.` + (r.admitted_next ? ` Допущены на следующий этап: ${r.admitted_next}.` : ''),
  )
}

async function createSlot() {
  if (!slot.starts_at) {
    error.value = 'Укажите время начала слота'
    return
  }
  await run(
    () => addSlot(props.event.id, stageId.value, {
      ...slot,
      starts_at: new Date(slot.starts_at).toISOString(),
      ends_at: slot.ends_at ? new Date(slot.ends_at).toISOString() : null,
    }),
    'Слот добавлен',
  )
  Object.assign(slot, { title: '', room: '', starts_at: '', ends_at: '' })
}

function slotLabel(s) {
  const start = new Date(s.starts_at)
  const time = start.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  return [time, s.room && `ауд. ${s.room}`, s.title].filter(Boolean).join(' · ')
}

watch(stageId, load, { immediate: true })
</script>

<template>
  <div class="grid gap-6">
    <p v-if="!stages.length" class="text-ink-muted">У мероприятия нет этапов. Добавьте их на вкладке «Этапы».</p>

    <div v-else class="flex flex-wrap gap-2" role="tablist" aria-label="Этап">
      <button
        v-for="(stage, index) in stages"
        :key="stage.id"
        type="button"
        role="tab"
        :aria-selected="stageId === stage.id"
        class="rounded-full border px-3 py-1 text-sm"
        :class="stageId === stage.id ? 'border-brand-500 bg-brand-100 text-brand-700' : 'border-line bg-surface text-ink-muted hover:text-ink'"
        @click="stageId = stage.id"
      >
        {{ index + 1 }}. {{ stage.title }}
      </button>
    </div>

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <p v-if="notice" role="status" class="rounded-control bg-green-100 px-4 py-3 text-green-800">{{ notice }}</p>

    <template v-if="data">
      <div v-if="manage" class="flex flex-wrap items-center gap-3">
        <UiButton @click="run(() => admitToStage(event.id, stageId), 'Участники допущены')">
          {{ isFirst ? 'Допустить принятые заявки' : 'Допустить прошедших предыдущий этап' }}
        </UiButton>
        <a :href="programUrl(event.id, stageId)" class="rounded-control border border-line bg-surface px-3 py-2 text-sm hover:bg-brand-50">Программа защит в Excel</a>
      </div>

      <UiCard v-if="manage && data.participants.length">
        <template #title>Переход {{ data.has_next ? `на этап «${data.next_title}»` : 'к итогам' }}</template>
        <form class="flex flex-wrap items-end gap-4 text-sm" @submit.prevent="run(() => setStageRule(event.id, stageId, rule), 'Правило сохранено')">
          <label class="grid gap-1">
            <span class="font-medium">Правило</span>
            <select v-model="rule.type" class="h-10 rounded-control border border-line bg-surface px-3">
              <option value="top_n">Лучшие N</option>
              <option value="threshold">Проходной балл</option>
              <option value="manual">Решение оргкомитета</option>
            </select>
          </label>
          <label v-if="rule.type === 'top_n'" class="grid gap-1">
            <span class="font-medium">Сколько проходит</span>
            <input v-model.number="rule.n" type="number" min="1" class="h-10 w-24 rounded-control border border-line bg-surface px-3" />
          </label>
          <label v-if="rule.type === 'top_n'" class="flex h-10 items-center gap-2">
            <input v-model="rule.per_direction" type="checkbox" class="size-4 accent-brand-600" /> в каждом направлении
          </label>
          <label v-if="rule.type === 'threshold'" class="grid gap-1">
            <span class="font-medium">Не меньше баллов</span>
            <input v-model.number="rule.threshold" type="number" step="0.5" class="h-10 w-28 rounded-control border border-line bg-surface px-3" />
          </label>
          <UiButton type="submit">Показать предложение</UiButton>
        </form>
        <p class="mt-3 text-sm text-ink-muted">
          Предложение можно поправить в таблице. При равенстве баллов на границе проходят все.
        </p>
        <div class="mt-4 flex flex-wrap items-center gap-2">
          <UiButton v-if="!confirmApply" variant="primary" :disabled="!pending" @click="confirmApply = true">Применить решения ({{ pending }})</UiButton>
          <template v-else>
            <span class="text-sm">Отметить прошедших{{ data.has_next ? ' и допустить их на следующий этап' : '' }}?</span>
            <UiButton size="sm" variant="primary" @click="apply">Применить</UiButton>
            <UiButton size="sm" variant="ghost" @click="confirmApply = false">Отмена</UiButton>
          </template>
        </div>
      </UiCard>

      <div class="overflow-x-auto rounded-card border border-line bg-surface">
        <SkeletonTable v-if="loading && !data.participants.length" :rows="4" :columns="6" />
        <table v-else class="w-full text-sm">
          <thead class="bg-canvas text-left text-xs text-ink-muted">
            <tr>
              <th class="px-3 py-2">Место</th>
              <th class="px-3 py-2">Работа</th>
              <th class="px-3 py-2 text-right">Балл</th>
              <th class="px-3 py-2">Статус</th>
              <th class="px-3 py-2">Защита</th>
              <th v-if="manage" class="px-3 py-2">Решение</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in data.participants" :key="p.id" class="border-t border-line" :class="{ 'opacity-60': p.status === 'withdrawn' }">
              <td class="px-3 py-2 font-semibold tabular-nums">{{ p.rank ?? '—' }}</td>
              <td class="px-3 py-2">
                <p class="font-medium">№{{ p.number }} · {{ p.title || 'Без названия' }}</p>
                <p class="text-xs text-ink-muted">{{ p.participants.join(', ') }}<span v-if="p.direction"> · {{ p.direction }}</span></p>
              </td>
              <td class="px-3 py-2 text-right font-semibold tabular-nums text-score-600">{{ formatPoints(p.score) }}</td>
              <td class="px-3 py-2"><UiBadge :tone="STAGE_STATUS_TONES[p.status]">{{ STAGE_STATUS_LABELS[p.status] }}</UiBadge></td>
              <td class="px-3 py-2">
                <select
                  v-if="manage && data.slots.length"
                  :value="p.slot_id ?? ''"
                  aria-label="Слот защиты"
                  class="h-8 max-w-56 rounded-control border border-line bg-surface px-2"
                  @change="run(() => updateParticipant(p.id, $event.target.value ? { slot_id: Number($event.target.value) } : { clear_slot: true }), 'Расписание обновлено')"
                >
                  <option value="">Не назначена</option>
                  <option v-for="s in data.slots" :key="s.id" :value="s.id">{{ slotLabel(s) }}</option>
                </select>
                <span v-else class="text-ink-muted">{{ data.slots.find((s) => s.id === p.slot_id) ? slotLabel(data.slots.find((s) => s.id === p.slot_id)) : '—' }}</span>
              </td>
              <td v-if="manage" class="px-3 py-2">
                <select v-if="p.status !== 'withdrawn'" v-model="decisions[p.id]" aria-label="Решение" class="h-8 rounded-control border border-line bg-surface px-2">
                  <option :value="null">—</option>
                  <option value="passed">Прошёл</option>
                  <option value="not_passed">Не прошёл</option>
                </select>
                <UiButton v-if="p.status !== 'withdrawn'" size="sm" variant="ghost" @click="run(() => updateParticipant(p.id, { status: 'withdrawn' }), 'Участник снят с этапа')">Снять</UiButton>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!loading && !data.participants.length" class="px-4 py-8 text-center text-ink-muted">
          На этапе пока нет участников. {{ manage ? 'Допустите их кнопкой выше.' : '' }}
        </p>
      </div>

      <UiCard v-if="manage">
        <template #title>Слоты защит</template>
        <ul v-if="data.slots.length" class="mb-4 divide-y divide-line">
          <li v-for="s in data.slots" :key="s.id" class="flex items-center gap-3 py-2 text-sm">
            <span class="flex-1">{{ slotLabel(s) }}</span>
            <span class="text-ink-muted">работ: {{ s.participants }}</span>
            <UiButton size="sm" variant="ghost" @click="run(() => deleteSlot(s.id), 'Слот удалён')">Удалить</UiButton>
          </li>
        </ul>
        <form class="grid gap-3 text-sm sm:grid-cols-4" @submit.prevent="createSlot">
          <input v-model="slot.starts_at" type="datetime-local" aria-label="Начало" class="h-10 rounded-control border border-line bg-surface px-3" />
          <input v-model="slot.ends_at" type="datetime-local" aria-label="Окончание" class="h-10 rounded-control border border-line bg-surface px-3" />
          <input v-model="slot.room" placeholder="Аудитория" aria-label="Аудитория" class="h-10 rounded-control border border-line bg-surface px-3" />
          <input v-model="slot.title" placeholder="Секция" aria-label="Название" class="h-10 rounded-control border border-line bg-surface px-3" />
          <div class="sm:col-span-4"><UiButton type="submit" size="sm">Добавить слот</UiButton></div>
        </form>
      </UiCard>
    </template>
    <SkeletonTable v-else-if="loading" :rows="4" :columns="5" />
  </div>
</template>
