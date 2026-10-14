<script setup>
/** Поле анкеты заявки по его типу. Для файла загружает его и хранит id. */
import { computed, ref, useId } from 'vue'
import { uploadFile } from '@/api/applications'
import { errorMessage } from '@/api/http'

const props = defineProps({
  field: { type: Object, required: true },
  error: { type: String, default: '' },
  files: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})
const model = defineModel({ type: [String, Number, Boolean, Array, null], default: null })
const id = useId()
const uploading = ref(false)
const uploadError = ref('')
const uploaded = ref(null)

const currentFile = computed(() => uploaded.value ?? props.files.find((f) => f.id === model.value) ?? null)
const inputType = { email: 'email', phone: 'tel', url: 'url', date: 'date', number: 'number' }
const placeholder = { email: 'name@example.ru', phone: '+7 900 000-00-00', url: 'https://' }

function toggle(option, checked) {
  const list = Array.isArray(model.value) ? [...model.value] : []
  model.value = checked ? [...list, option] : list.filter((v) => v !== option)
}

async function pickFile(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploadError.value = ''
  uploading.value = true
  try {
    const stored = await uploadFile(file)
    uploaded.value = { id: stored.id, name: stored.name, size: stored.size }
    model.value = stored.id
  } catch (e) {
    uploadError.value = errorMessage(e)
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}

function size(bytes) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} МБ` : `${Math.max(1, Math.round(bytes / 1024))} КБ`
}
</script>

<template>
  <div class="grid gap-1.5">
    <label v-if="field.type !== 'checkbox'" :for="id" class="text-sm font-medium">
      {{ field.label }}<span v-if="field.required" class="text-red-600" aria-hidden="true"> *</span>
    </label>

    <textarea
      v-if="field.type === 'textarea'"
      :id="id" v-model="model" rows="4" :disabled="disabled"
      class="rounded-control border bg-surface px-3 py-2" :class="error ? 'border-red-500' : 'border-line'"
    />
    <select
      v-else-if="field.type === 'select'"
      :id="id" v-model="model" :disabled="disabled"
      class="h-10 rounded-control border bg-surface px-3" :class="error ? 'border-red-500' : 'border-line'"
    >
      <option :value="null">Не выбрано</option>
      <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
    </select>
    <fieldset v-else-if="field.type === 'multiselect'" :id="id" class="grid gap-1.5" :disabled="disabled">
      <label v-for="option in field.options" :key="option" class="flex items-center gap-2">
        <input type="checkbox" class="size-4 accent-brand-600" :checked="model?.includes(option)" @change="toggle(option, $event.target.checked)" />
        {{ option }}
      </label>
    </fieldset>
    <label v-else-if="field.type === 'checkbox'" class="flex items-start gap-2">
      <input :id="id" v-model="model" type="checkbox" class="mt-1 size-4 accent-brand-600" :disabled="disabled" />
      <span class="text-sm font-medium">{{ field.label }}<span v-if="field.required" class="text-red-600" aria-hidden="true"> *</span></span>
    </label>
    <div v-else-if="field.type === 'file'" class="flex flex-wrap items-center gap-3">
      <span v-if="currentFile" class="text-sm">{{ currentFile.name }} · {{ size(currentFile.size) }}</span>
      <label v-if="!disabled" class="cursor-pointer rounded-control border border-line bg-surface px-3 py-2 text-sm hover:bg-brand-50">
        {{ uploading ? 'Загрузка…' : currentFile ? 'Заменить файл' : 'Выбрать файл' }}
        <input :id="id" type="file" class="sr-only" :disabled="uploading" @change="pickFile" />
      </label>
      <button v-if="currentFile && !disabled" type="button" class="text-sm text-ink-muted hover:text-ink" @click="model = null; uploaded = null">Убрать</button>
    </div>
    <input
      v-else
      :id="id"
      v-model="model"
      :type="inputType[field.type] ?? 'text'"
      :placeholder="placeholder[field.type]"
      :disabled="disabled"
      class="h-10 rounded-control border bg-surface px-3" :class="error ? 'border-red-500' : 'border-line'"
      @change="field.type === 'number' && model !== '' && (model = Number(model))"
    />

    <p v-if="error || uploadError" class="text-sm text-red-600">{{ error || uploadError }}</p>
    <p v-else-if="field.help" class="text-sm text-ink-muted">{{ field.help }}</p>
  </div>
</template>
