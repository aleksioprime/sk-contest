<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { formatPoints } from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import { AWARD_LABELS, AWARD_TONES, diplomaUrl, diplomasUrl, fetchResults, publishResults, saveAwards } from '@/api/stages'
import SkeletonTable from '@/components/skeleton/SkeletonTable.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'

const props = defineProps({ event: { type: Object, required: true } })

const results = ref(null)
const awards = reactive({
  rank_scope: 'direction',
  nominations: [],
  winners: 1,
  prize_places: 3,
  stage_id: null,
  signatory: '',
  signatory_title: '',
  date_text: '',
})
const nominationTitle = ref('')
const error = ref('')
const notice = ref('')
const confirmPublish = ref(false)

const manage = computed(() => props.event.can_manage)
const groups = computed(() => {
  const map = new Map()
  const overall = results.value?.awards.rank_scope === 'overall'
  for (const row of results.value?.rows ?? []) {
    const key = overall ? 'Общий рейтинг' : row.direction || 'Без направления'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(row)
  }
  return [...map.entries()]
})

async function load() {
  error.value = ''
  try {
    results.value = await fetchResults(props.event.id)
    Object.assign(awards, results.value.awards)
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function run(fn, message) {
  error.value = ''
  notice.value = ''
  try {
    await fn()
    await load()
    notice.value = message
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function togglePublish() {
  confirmPublish.value = false
  const publish = !results.value.published_at
  await run(() => publishResults(props.event.id, publish), publish ? 'Итоги опубликованы: участники видят места и дипломы' : 'Итоги скрыты')
}

const workLabel = (id) => {
  const row = results.value?.rows.find((r) => r.application_id === id)
  return row ? `№${row.number} · ${row.title || 'Без названия'}` : `Заявка ${id}`
}

async function saveNominations(nominations, message) {
  await run(() => saveAwards(props.event.id, { ...awards, nominations }), message)
}

function addNomination() {
  const title = nominationTitle.value.trim()
  if (!title) return
  nominationTitle.value = ''
  saveNominations([...awards.nominations, { id: `n${Date.now().toString(36)}`, title, application_ids: [] }], `Номинация «${title}» добавлена`)
}

function assign(nomination, applicationId, add) {
  const ids = add ? [...new Set([...nomination.application_ids, applicationId])] : nomination.application_ids.filter((i) => i !== applicationId)
  saveNominations(
    awards.nominations.map((n) => (n.id === nomination.id ? { ...n, application_ids: ids } : n)),
    'Номинации сохранены',
  )
}

function removeNomination(nomination) {
  saveNominations(awards.nominations.filter((n) => n.id !== nomination.id), `Номинация «${nomination.title}» удалена`)
}

onMounted(load)
</script>

<template>
  <div class="grid gap-6">
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <p v-if="notice" role="status" class="rounded-control bg-green-100 px-4 py-3 text-green-800">{{ notice }}</p>

    <SkeletonTable v-if="!results && !error" :rows="5" :columns="4" />

    <template v-if="results">
      <div class="flex flex-wrap items-center gap-3">
        <UiBadge :tone="results.published_at ? 'success' : 'neutral'">
          {{ results.published_at ? `Опубликованы ${new Date(results.published_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })}` : 'Не опубликованы' }}
        </UiBadge>
        <template v-if="manage">
          <UiButton v-if="!confirmPublish" :variant="results.published_at ? 'secondary' : 'primary'" @click="confirmPublish = true">
            {{ results.published_at ? 'Скрыть итоги' : 'Опубликовать итоги' }}
          </UiButton>
          <span v-else class="flex flex-wrap items-center gap-2 text-sm">
            {{ results.published_at ? 'Скрыть итоги от участников и с лендинга?' : 'Участники увидят свои места и смогут скачать дипломы. Победители появятся на лендинге.' }}
            <UiButton size="sm" variant="primary" @click="togglePublish">Подтвердить</UiButton>
            <UiButton size="sm" variant="ghost" @click="confirmPublish = false">Отмена</UiButton>
          </span>
        </template>
        <a v-if="results.rows.length" :href="diplomasUrl(event.id)" class="ml-auto rounded-control border border-line bg-surface px-3 py-2 text-sm hover:bg-brand-50">Все дипломы (PDF)</a>
      </div>

      <section v-for="[direction, rows] in groups" :key="direction" class="grid gap-2">
        <h2 class="text-lg font-semibold">{{ direction }}</h2>
        <div class="overflow-x-auto rounded-card border border-line bg-surface">
          <table class="w-full text-sm">
            <thead class="bg-canvas text-left text-xs text-ink-muted">
              <tr>
                <th class="px-3 py-2">Место</th><th class="px-3 py-2">Работа</th><th class="px-3 py-2 text-right">Балл</th>
                <th class="px-3 py-2">Награда</th><th class="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.application_id" class="border-t border-line">
                <td class="px-3 py-2 font-semibold tabular-nums">{{ row.rank ?? '—' }}</td>
                <td class="px-3 py-2">
                  <p class="font-medium">№{{ row.number }} · {{ row.title || 'Без названия' }}</p>
                  <p class="text-xs text-ink-muted">{{ row.participants.join(', ') }}</p>
                </td>
                <td class="px-3 py-2 text-right font-semibold tabular-nums text-score-600">{{ formatPoints(row.score) }}</td>
                <td class="px-3 py-2">
                  <div class="flex flex-wrap gap-1">
                    <UiBadge :tone="AWARD_TONES[row.award]">{{ AWARD_LABELS[row.award] }}</UiBadge>
                    <UiBadge v-for="n in row.nominations" :key="n" tone="warning">{{ n }}</UiBadge>
                  </div>
                </td>
                <td class="px-3 py-2 text-right"><a :href="diplomaUrl(row.application_id)" class="text-brand-700 hover:underline">Диплом</a></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <p v-if="!results.rows.length" class="text-ink-muted">Пока нет участников с итогами. Они появятся, когда работы будут оценены.</p>

      <UiCard v-if="manage">
        <template #title>Номинации</template>
        <p class="text-sm text-ink-muted">Специальные награды сверх мест: «Лучший дизайн», «Приз зрительских симпатий». За каждую — отдельный диплом.</p>
        <ul class="mt-4 grid gap-3">
          <li v-for="nomination in awards.nominations" :key="nomination.id" class="rounded-control border border-line p-3 text-sm">
            <div class="flex items-center gap-2">
              <p class="min-w-0 flex-1 font-medium">{{ nomination.title }}</p>
              <UiButton size="sm" variant="ghost" @click="removeNomination(nomination)">Удалить</UiButton>
            </div>
            <ul class="mt-2 flex flex-wrap gap-2">
              <li v-for="id in nomination.application_ids" :key="id" class="flex items-center gap-1 rounded-full bg-canvas px-3 py-1">
                {{ workLabel(id) }}
                <button type="button" class="text-ink-muted hover:text-red-700" :aria-label="`Убрать ${workLabel(id)}`" @click="assign(nomination, id, false)">×</button>
              </li>
            </ul>
            <select class="mt-2 h-9 max-w-full rounded-control border border-line bg-surface px-2" aria-label="Добавить работу в номинацию" @change="(assign(nomination, Number($event.target.value), true), ($event.target.value = ''))">
              <option value="">+ Добавить работу…</option>
              <option v-for="row in results.rows.filter((r) => !nomination.application_ids.includes(r.application_id))" :key="row.application_id" :value="row.application_id">
                №{{ row.number }} · {{ row.title || 'Без названия' }}
              </option>
            </select>
          </li>
        </ul>
        <form class="mt-4 flex gap-2" @submit.prevent="addNomination">
          <input v-model="nominationTitle" placeholder="Название номинации" maxlength="200" class="h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 text-sm" />
          <UiButton type="submit">Добавить</UiButton>
        </form>
      </UiCard>

      <UiCard v-if="manage">
        <template #title>Награды и дипломы</template>
        <form class="grid gap-4 text-sm sm:grid-cols-3" @submit.prevent="run(() => saveAwards(event.id, awards), 'Настройки наград сохранены')">
          <label class="grid gap-1 sm:col-span-3">
            <span class="font-medium">Места и награды</span>
            <select v-model="awards.rank_scope" class="h-10 rounded-control border border-line bg-surface px-3 sm:max-w-md">
              <option value="direction">В каждом направлении отдельно</option>
              <option value="overall">Общий рейтинг без направлений</option>
            </select>
          </label>
          <label class="grid gap-1"><span class="font-medium">{{ awards.rank_scope === 'overall' ? 'Победителей' : 'Победителей в направлении' }}</span><input v-model.number="awards.winners" type="number" min="0" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label class="grid gap-1"><span class="font-medium">Призовых мест всего</span><input v-model.number="awards.prize_places" type="number" min="0" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label class="grid gap-1">
            <span class="font-medium">Итоги по этапу</span>
            <select v-model="awards.stage_id" class="h-10 rounded-control border border-line bg-surface px-3">
              <option :value="null">Последний этап с участниками</option>
              <option v-for="stage in event.stages" :key="stage.id" :value="stage.id">{{ stage.title }}</option>
            </select>
          </label>
          <label class="grid gap-1"><span class="font-medium">Подпись на дипломе</span><input v-model="awards.signatory" placeholder="И. И. Иванов" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label class="grid gap-1"><span class="font-medium">Должность</span><input v-model="awards.signatory_title" placeholder="Председатель жюри" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label class="grid gap-1"><span class="font-medium">Дата и место</span><input v-model="awards.date_text" placeholder="Москва, апрель 2027" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <div class="sm:col-span-3"><UiButton type="submit">Сохранить</UiButton></div>
        </form>
      </UiCard>
    </template>
  </div>
</template>
