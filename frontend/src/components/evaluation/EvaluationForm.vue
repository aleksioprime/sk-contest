<script setup>
/**
 * Оценка работы по критериям. Каждое изменение сразу сохраняется на сервере,
 * балл пересчитывается там же и возвращается в ответе.
 */
import { computed, ref, watch } from 'vue'
import { formatPoints } from '@/api/evaluation'
import { errorMessage } from '@/api/http'

const props = defineProps({
  bundle: { type: Object, required: true },
  client: { type: Object, required: true },
})
const emit = defineEmits(['update:bundle'])

const saving = ref(0)
const error = ref('')
const comments = ref({})
const generalComment = ref('')

const items = computed(() => Object.fromEntries(props.bundle.items.map((i) => [i.criterion_id, i])))
const categories = computed(() => {
  const { categories: list, criteria } = props.bundle.scorecard
  const groups = list.map((c) => ({ ...c, criteria: criteria.filter((x) => x.category_id === c.id) }))
  const rest = criteria.filter((x) => !x.category_id)
  if (rest.length) groups.push({ id: 0, title: list.length ? 'Другое' : '', criteria: rest })
  return groups.filter((g) => g.criteria.length)
})
const filled = computed(() => props.bundle.items.filter((i) => i.score !== null).length)
const total = computed(() => props.bundle.scorecard.criteria.length)

watch(
  () => props.bundle.evaluation_id,
  () => {
    comments.value = Object.fromEntries(props.bundle.items.map((i) => [i.criterion_id, i.comment]))
    generalComment.value = props.bundle.comment
  },
  { immediate: true },
)

async function send(fn) {
  saving.value += 1
  error.value = ''
  try {
    emit('update:bundle', await fn())
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value -= 1
  }
}

function pickLevel(criterion, level) {
  const current = items.value[criterion.id]?.level_id
  send(() => props.client.setCriterion(criterion.id, current === level.id ? { clear: true } : { level_id: level.id }))
}

function toggleOption(criterion, option) {
  const selected = items.value[criterion.id]?.option_ids ?? []
  const next = selected.includes(option.id) ? selected.filter((id) => id !== option.id) : [...selected, option.id]
  send(() => props.client.setCriterion(criterion.id, next.length ? { option_ids: next } : { clear: true }))
}

function saveCriterionComment(criterion) {
  if ((items.value[criterion.id]?.comment ?? '') === (comments.value[criterion.id] ?? '')) return
  send(() => props.client.setCriterion(criterion.id, { comment: comments.value[criterion.id] ?? '' }))
}

function saveGeneralComment() {
  if (generalComment.value === props.bundle.comment) return
  send(() => props.client.setComment(generalComment.value))
}
</script>

<template>
  <div class="grid gap-5">
    <div class="sticky top-14 z-[5] flex flex-wrap items-center gap-x-6 gap-y-1 rounded-card border border-score-600/30 bg-score-100 px-4 py-3">
      <span class="text-sm text-score-600">Ваш балл</span>
      <span class="text-2xl font-bold tabular-nums text-score-600">{{ formatPoints(bundle.score) }}</span>
      <span class="text-sm text-ink-muted">из {{ formatPoints(bundle.scorecard.max_score) }}</span>
      <span class="text-sm" :class="filled === total ? 'text-green-700' : 'text-ink-muted'">
        Оценено критериев: {{ filled }} из {{ total }}
      </span>
      <span class="ml-auto text-xs text-ink-muted" role="status">{{ saving ? 'Сохранение…' : 'Сохранено' }}</span>
    </div>

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <p v-if="!bundle.editable" class="rounded-control bg-canvas px-4 py-3 text-ink-muted">Оценка закрыта, изменения не сохраняются.</p>

    <section v-for="group in categories" :key="group.id" class="grid gap-3">
      <h2 v-if="group.title" class="text-lg font-semibold">{{ group.title }}</h2>
      <article
        v-for="criterion in group.criteria"
        :key="criterion.id"
        class="rounded-card border bg-surface p-4"
        :class="items[criterion.id]?.score != null ? 'border-line' : 'border-dashed border-brand-200'"
      >
        <div class="flex flex-wrap items-start justify-between gap-2">
          <h3 class="font-semibold">{{ criterion.title }}</h3>
          <span class="text-sm tabular-nums text-ink-muted">
            {{ formatPoints(items[criterion.id]?.score) }}<span v-if="Number(criterion.weight) !== 1"> × {{ formatPoints(criterion.weight) }}</span>
          </span>
        </div>
        <p v-if="criterion.description" class="mt-1 whitespace-pre-line text-sm text-ink-muted">{{ criterion.description }}</p>

        <div v-if="criterion.type === 'scale'" class="mt-3 flex flex-wrap gap-2" role="radiogroup" :aria-label="criterion.title">
          <button
            v-for="level in criterion.scale.levels"
            :key="level.id"
            type="button"
            role="radio"
            :aria-checked="items[criterion.id]?.level_id === level.id"
            :disabled="!bundle.editable"
            class="min-w-24 rounded-control border px-3 py-2 text-left text-sm transition-colors disabled:opacity-70"
            :class="items[criterion.id]?.level_id === level.id ? 'border-brand-600 bg-brand-600 text-white' : 'border-line bg-surface hover:border-brand-500'"
            @click="pickLevel(criterion, level)"
          >
            <span class="block font-semibold tabular-nums">{{ formatPoints(level.points) }}</span>
            <span class="block text-xs" :class="items[criterion.id]?.level_id === level.id ? 'text-white/85' : 'text-ink-muted'">{{ level.title }}</span>
          </button>
        </div>

        <div v-else class="mt-3 grid gap-2">
          <label
            v-for="option in criterion.options"
            :key="option.id"
            class="flex items-start gap-3 rounded-control border px-3 py-2 text-sm"
            :class="items[criterion.id]?.option_ids.includes(option.id) ? 'border-brand-500 bg-brand-50' : 'border-line'"
          >
            <input
              type="checkbox"
              class="mt-0.5 size-4 accent-brand-600"
              :checked="items[criterion.id]?.option_ids.includes(option.id)"
              :disabled="!bundle.editable"
              @change="toggleOption(criterion, option)"
            />
            <span class="flex-1">{{ option.title }}<span v-if="option.is_exclusive" class="text-ink-muted"> · снимает остальные</span></span>
            <span class="tabular-nums text-ink-muted">{{ formatPoints(option.points) }}</span>
          </label>
        </div>

        <details class="mt-3 text-sm" :open="!!items[criterion.id]?.comment">
          <summary class="cursor-pointer text-ink-muted">Комментарий к критерию</summary>
          <textarea
            v-model="comments[criterion.id]"
            rows="2"
            :disabled="!bundle.editable"
            class="mt-2 w-full rounded-control border border-line bg-surface px-3 py-2"
            @blur="saveCriterionComment(criterion)"
          />
        </details>
      </article>
    </section>

    <label class="grid gap-1.5">
      <span class="font-semibold">Общий комментарий</span>
      <textarea
        v-model="generalComment"
        rows="3"
        :disabled="!bundle.editable"
        class="rounded-control border border-line bg-surface px-3 py-2"
        placeholder="Что получилось, что стоит доработать"
        @blur="saveGeneralComment"
      />
    </label>
  </div>
</template>
