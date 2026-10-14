<script setup>
import { reactive, ref } from 'vue'
import { createScale, updateScale } from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({
  eventId: { type: Number, required: true },
  scale: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'cancel'])

const draft = reactive({
  title: props.scale?.title ?? '',
  levels: props.scale?.levels.map(({ title, points }) => ({ title, points: Number(points) })) ?? [
    { title: 'Не выполнено', points: 0 },
    { title: 'Частично', points: 1 },
    { title: 'Полностью', points: 2 },
  ],
})
const error = ref('')
const saving = ref(false)

async function save() {
  saving.value = true
  error.value = ''
  try {
    const saved = props.scale ? await updateScale(props.scale.id, draft) : await createScale(props.eventId, draft)
    emit('saved', saved)
  } catch (e) {
    const detail = e?.response?.data?.detail
    error.value = Array.isArray(detail) ? 'Заполните название и минимум два уровня' : errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="grid gap-3 rounded-card border border-brand-200 bg-surface p-4" @submit.prevent="save">
    <label class="grid gap-1 text-sm">
      <span class="font-medium">Название шкалы</span>
      <input v-model="draft.title" placeholder="Например, 0–2 балла" class="h-10 rounded-control border border-line bg-surface px-3" />
    </label>
    <div class="grid gap-2">
      <span class="text-sm font-medium">Уровни</span>
      <div v-for="(level, index) in draft.levels" :key="index" class="flex gap-2">
        <input v-model.number="level.points" type="number" step="0.5" aria-label="Баллы" class="h-10 w-24 rounded-control border border-line bg-surface px-3" />
        <input v-model="level.title" placeholder="Описание уровня" aria-label="Описание уровня" class="h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3" />
        <UiButton size="sm" variant="ghost" :disabled="draft.levels.length <= 2" @click="draft.levels.splice(index, 1)">Убрать</UiButton>
      </div>
      <div><UiButton size="sm" @click="draft.levels.push({ title: '', points: draft.levels.length })">Добавить уровень</UiButton></div>
    </div>
    <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
    <div class="flex gap-2">
      <UiButton type="submit" size="sm" variant="primary" :loading="saving">Сохранить шкалу</UiButton>
      <UiButton size="sm" variant="ghost" @click="emit('cancel')">Отмена</UiButton>
    </div>
  </form>
</template>
