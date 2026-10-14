<script setup>
/**
 * Редактор упорядоченного списка: направления, этапы или формы участия.
 * fields: [{ key, label, type: 'text' | 'textarea' | 'date' | 'select', options?: { value: label } }]
 */
import { reactive, ref } from 'vue'
import { addChild, deleteChild, reorderChildren, updateChild } from '@/api/events'
import { errorMessage } from '@/api/http'
import EventItemFields from '@/components/events/EventItemFields.vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({
  eventId: { type: Number, required: true },
  kind: { type: String, required: true },
  items: { type: Array, required: true },
  fields: { type: Array, required: true },
  emptyText: { type: String, default: 'Пока пусто' },
  addLabel: { type: String, default: 'Добавить' },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['update:items'])

const editingId = ref(null) // id или 'new'
const draft = reactive({})
const error = ref('')
const saving = ref(false)

function blank() {
  return Object.fromEntries(props.fields.map((f) => [f.key, f.type === 'select' ? Object.keys(f.options)[0] : '']))
}

function startEdit(item) {
  error.value = ''
  editingId.value = item ? item.id : 'new'
  Object.assign(draft, blank(), item ? Object.fromEntries(props.fields.map((f) => [f.key, item[f.key] ?? ''])) : {})
}

function payload() {
  return Object.fromEntries(props.fields.map((f) => [f.key, f.type === 'date' && !draft[f.key] ? null : draft[f.key]]))
}

async function save() {
  if (!String(draft[props.fields[0].key] ?? '').trim()) {
    error.value = `Заполните поле «${props.fields[0].label}»`
    return
  }
  saving.value = true
  error.value = ''
  try {
    if (editingId.value === 'new') {
      emit('update:items', [...props.items, await addChild(props.eventId, props.kind, payload())])
    } else {
      const saved = await updateChild(props.eventId, props.kind, editingId.value, payload())
      emit('update:items', props.items.map((item) => (item.id === saved.id ? saved : item)))
    }
    editingId.value = null
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function remove(item) {
  error.value = ''
  try {
    await deleteChild(props.eventId, props.kind, item.id)
    emit('update:items', props.items.filter((other) => other.id !== item.id))
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function move(index, delta) {
  const list = [...props.items]
  const [item] = list.splice(index, 1)
  list.splice(index + delta, 0, item)
  emit('update:items', list)
  try {
    await reorderChildren(props.eventId, props.kind, list.map((other) => other.id))
  } catch (e) {
    error.value = errorMessage(e)
  }
}

function summary(item) {
  return props.fields
    .slice(1)
    .map((f) => (f.type === 'select' ? f.options[item[f.key]] : f.type === 'date' && item[f.key] ? new Date(item[f.key]).toLocaleDateString('ru-RU') : ''))
    .filter(Boolean)
    .join(' · ')
}
</script>

<template>
  <div class="grid gap-3">
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>

    <ol class="grid gap-2">
      <li v-for="(item, index) in items" :key="item.id" class="rounded-control border border-line bg-surface">
        <form v-if="editingId === item.id" class="grid gap-3 p-4" @submit.prevent="save">
          <EventItemFields v-model:draft="draft" :fields="fields" />
          <div class="flex gap-2">
            <UiButton type="submit" size="sm" variant="primary" :loading="saving">Сохранить</UiButton>
            <UiButton size="sm" variant="ghost" @click="editingId = null">Отмена</UiButton>
          </div>
        </form>
        <div v-else class="flex items-center gap-3 px-4 py-3">
          <span class="w-6 text-sm text-ink-muted tabular-nums">{{ index + 1 }}</span>
          <div class="min-w-0 flex-1">
            <p class="font-medium">{{ item[fields[0].key] }}</p>
            <p v-if="summary(item)" class="text-sm text-ink-muted">{{ summary(item) }}</p>
          </div>
          <div v-if="!readonly" class="flex gap-1">
            <UiButton size="sm" variant="ghost" :disabled="index === 0" aria-label="Выше" @click="move(index, -1)">↑</UiButton>
            <UiButton size="sm" variant="ghost" :disabled="index === items.length - 1" aria-label="Ниже" @click="move(index, 1)">↓</UiButton>
            <UiButton size="sm" variant="ghost" @click="startEdit(item)">Изменить</UiButton>
            <UiButton size="sm" variant="ghost" @click="remove(item)">Удалить</UiButton>
          </div>
        </div>
      </li>
    </ol>
    <p v-if="!items.length && editingId !== 'new'" class="text-sm text-ink-muted">{{ emptyText }}</p>

    <form v-if="editingId === 'new'" class="grid gap-3 rounded-control border border-brand-200 bg-surface p-4" @submit.prevent="save">
      <EventItemFields v-model:draft="draft" :fields="fields" />
      <div class="flex gap-2">
        <UiButton type="submit" size="sm" variant="primary" :loading="saving">Добавить</UiButton>
        <UiButton size="sm" variant="ghost" @click="editingId = null">Отмена</UiButton>
      </div>
    </form>
    <div v-else-if="!readonly"><UiButton size="sm" @click="startEdit(null)">{{ addLabel }}</UiButton></div>
  </div>
</template>
