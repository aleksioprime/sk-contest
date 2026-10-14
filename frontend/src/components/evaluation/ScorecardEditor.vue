<script setup>
/** Редактор таблицы оценок: категории и критерии (шкала или чек-лист), веса. */
import { reactive, ref } from 'vue'
import { createScorecard, updateScorecard } from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({
  eventId: { type: Number, required: true },
  scales: { type: Array, required: true },
  scorecard: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'cancel'])

function fromScorecard(card) {
  const categoryIndex = Object.fromEntries(card.categories.map((c, i) => [c.id, i]))
  return {
    title: card.title,
    categories: card.categories.map((c) => c.title),
    criteria: card.criteria.map((c) => ({
      title: c.title,
      description: c.description,
      type: c.type,
      scale_id: c.scale_id,
      weight: Number(c.weight),
      category: c.category_id ? categoryIndex[c.category_id] : null,
      options: c.options.map(({ title, points, is_exclusive }) => ({ title, points: Number(points), is_exclusive })),
    })),
  }
}

const draft = reactive(props.scorecard ? fromScorecard(props.scorecard) : { title: '', categories: [], criteria: [] })
const error = ref('')
const saving = ref(false)

function addCriterion() {
  draft.criteria.push({
    title: '', description: '', type: 'scale', scale_id: props.scales[0]?.id ?? null, weight: 1,
    category: draft.categories.length ? 0 : null, options: [],
  })
}

function addOption(criterion) {
  criterion.options.push({ title: '', points: 1, is_exclusive: false })
}

function removeCategory(index) {
  draft.categories.splice(index, 1)
  for (const criterion of draft.criteria) {
    if (criterion.category === index) criterion.category = null
    else if (criterion.category > index) criterion.category -= 1
  }
}

function move(index, delta) {
  const [item] = draft.criteria.splice(index, 1)
  draft.criteria.splice(index + delta, 0, item)
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const saved = props.scorecard ? await updateScorecard(props.scorecard.id, draft) : await createScorecard(props.eventId, draft)
    emit('saved', saved)
  } catch (e) {
    const detail = e?.response?.data?.detail
    error.value = Array.isArray(detail) ? detail.map((d) => d.msg.replace(/^Value error, /, '')).join('. ') : errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="grid gap-5 rounded-card border border-brand-200 bg-surface p-5" @submit.prevent="save">
    <label class="grid gap-1 text-sm">
      <span class="font-medium">Название таблицы</span>
      <input v-model="draft.title" placeholder="Например, Критерии защиты проектов" class="h-10 rounded-control border border-line bg-surface px-3" />
    </label>

    <div class="grid gap-2">
      <span class="text-sm font-medium">Категории критериев</span>
      <div v-for="(category, index) in draft.categories" :key="index" class="flex gap-2">
        <input v-model="draft.categories[index]" aria-label="Название категории" class="h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3" />
        <UiButton size="sm" variant="ghost" @click="removeCategory(index)">Убрать</UiButton>
      </div>
      <div><UiButton size="sm" @click="draft.categories.push('')">Добавить категорию</UiButton></div>
    </div>

    <div class="grid gap-3">
      <span class="text-sm font-medium">Критерии</span>
      <p v-if="!scales.length" class="text-sm text-amber-800">Сначала создайте шкалу, чтобы добавить критерий со шкалой. Чек-листу шкала не нужна.</p>
      <div v-for="(criterion, index) in draft.criteria" :key="index" class="grid gap-3 rounded-control border border-line p-4">
        <div class="grid gap-3 sm:grid-cols-[3fr_1fr]">
          <input v-model="criterion.title" placeholder="Критерий" aria-label="Название критерия" class="h-10 rounded-control border border-line bg-surface px-3" />
          <select v-model="criterion.type" aria-label="Тип критерия" class="h-10 rounded-control border border-line bg-surface px-3">
            <option value="scale">Шкала</option>
            <option value="checklist">Чек-лист</option>
          </select>
        </div>
        <textarea v-model="criterion.description" rows="2" placeholder="Пояснение для судей" aria-label="Пояснение" class="rounded-control border border-line bg-surface px-3 py-2 text-sm" />
        <div class="flex flex-wrap items-center gap-3 text-sm">
          <label v-if="criterion.type === 'scale'" class="flex items-center gap-2">
            Шкала
            <select v-model="criterion.scale_id" class="h-9 rounded-control border border-line bg-surface px-2">
              <option v-for="scale in scales" :key="scale.id" :value="scale.id">{{ scale.title }}</option>
            </select>
          </label>
          <label v-if="draft.categories.length" class="flex items-center gap-2">
            Категория
            <select v-model="criterion.category" class="h-9 rounded-control border border-line bg-surface px-2">
              <option :value="null">Без категории</option>
              <option v-for="(category, i) in draft.categories" :key="i" :value="i">{{ category || `Категория ${i + 1}` }}</option>
            </select>
          </label>
          <label class="flex items-center gap-2">
            Вес
            <input v-model.number="criterion.weight" type="number" min="0.1" step="0.1" class="h-9 w-20 rounded-control border border-line bg-surface px-2" />
          </label>
          <span class="ml-auto flex gap-1">
            <UiButton size="sm" variant="ghost" :disabled="index === 0" aria-label="Выше" @click="move(index, -1)">↑</UiButton>
            <UiButton size="sm" variant="ghost" :disabled="index === draft.criteria.length - 1" aria-label="Ниже" @click="move(index, 1)">↓</UiButton>
            <UiButton size="sm" variant="ghost" @click="draft.criteria.splice(index, 1)">Удалить</UiButton>
          </span>
        </div>
        <div v-if="criterion.type === 'checklist'" class="grid gap-2 border-t border-line pt-3">
          <div v-for="(option, j) in criterion.options" :key="j" class="flex flex-wrap items-center gap-2 text-sm">
            <input v-model="option.title" placeholder="Пункт" aria-label="Пункт чек-листа" class="h-9 min-w-0 flex-1 rounded-control border border-line bg-surface px-3" />
            <input v-model.number="option.points" type="number" step="0.5" aria-label="Баллы" class="h-9 w-20 rounded-control border border-line bg-surface px-2" />
            <label class="flex items-center gap-1"><input v-model="option.is_exclusive" type="checkbox" class="size-4 accent-brand-600" /> снимает остальные</label>
            <UiButton size="sm" variant="ghost" @click="criterion.options.splice(j, 1)">Убрать</UiButton>
          </div>
          <div><UiButton size="sm" @click="addOption(criterion)">Добавить пункт</UiButton></div>
        </div>
      </div>
      <div><UiButton size="sm" @click="addCriterion">Добавить критерий</UiButton></div>
    </div>

    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
    <div class="flex gap-2">
      <UiButton type="submit" variant="primary" :loading="saving">Сохранить таблицу</UiButton>
      <UiButton variant="ghost" @click="emit('cancel')">Отмена</UiButton>
    </div>
  </form>
</template>
