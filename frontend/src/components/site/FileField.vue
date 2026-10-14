<script setup>
import { ref } from 'vue'
import { errorMessage } from '@/api/http'
import { uploadAsset } from '@/api/sites'

defineProps({ label: { type: String, default: '' } })
const value = defineModel({ type: Object, default: null })
const uploading = ref(false)
const error = ref('')
const input = ref(null)

async function pick(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    value.value = await uploadAsset(file, file.name, 'site_document')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="grid gap-1.5 text-sm">
    <span v-if="label" class="font-medium">{{ label }}</span>
    <div class="flex flex-wrap items-center gap-2">
      <a v-if="value" :href="value.url" target="_blank" rel="noopener" class="min-w-0 truncate text-brand-700 hover:underline">{{ value.name || 'Файл' }}</a>
      <button type="button" class="rounded-control border border-line px-2.5 py-1 hover:bg-brand-50" :disabled="uploading" @click="input.click()">
        {{ uploading ? 'Загрузка…' : value ? 'Заменить' : 'Загрузить файл' }}
      </button>
    </div>
    <p class="text-xs text-ink-muted">Файл будет доступен всем по ссылке. PDF, Word, Excel, PowerPoint до 25 МБ.</p>
    <input ref="input" type="file" class="hidden" @change="pick" />
    <p v-if="error" class="text-red-700">{{ error }}</p>
  </div>
</template>
