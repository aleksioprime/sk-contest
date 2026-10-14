<script setup>
import { ref } from 'vue'
import { errorMessage } from '@/api/http'
import { uploadAsset } from '@/api/sites'
import ImageCropper from './ImageCropper.vue'

const props = defineProps({
  label: { type: String, default: '' },
  ratio: { type: String, default: '16:9' },
})
const value = defineModel({ type: Object, default: null })

const picked = ref(null)
const uploading = ref(false)
const error = ref('')
const input = ref(null)

function pick(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    error.value = 'Подойдёт JPG, PNG или WebP'
    return
  }
  error.value = ''
  picked.value = file
  if (props.ratio === 'free') upload(null)
}

async function upload(blob) {
  const file = picked.value
  picked.value = null
  uploading.value = true
  try {
    // Логотипы без кадрирования сохраняют прозрачность PNG
    const asset = await uploadAsset(blob ?? file, blob ? file.name.replace(/\.\w+$/, '.jpg') : file.name)
    value.value = { ...asset, alt: value.value?.alt ?? '' }
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
    <div class="flex items-start gap-3">
      <img v-if="value?.url" :src="value.url" alt="" class="size-16 shrink-0 rounded-control border border-line object-cover" />
      <div v-else class="grid size-16 shrink-0 place-items-center rounded-control border border-dashed border-line text-xs text-ink-muted">нет</div>
      <div class="grid min-w-0 flex-1 gap-1.5">
        <div class="flex flex-wrap gap-2">
          <button type="button" class="rounded-control border border-line px-2.5 py-1 hover:bg-brand-50" :disabled="uploading" @click="input.click()">
            {{ uploading ? 'Загрузка…' : value ? 'Заменить' : 'Загрузить' }}
          </button>
          <button v-if="value" type="button" class="rounded-control px-2.5 py-1 text-ink-muted hover:bg-brand-50" @click="value = null">Убрать</button>
        </div>
        <input
          v-if="value"
          :value="value.alt"
          placeholder="Описание для незрячих"
          aria-label="Описание картинки"
          class="h-8 rounded-control border border-line bg-surface px-2"
          @change="value = { ...value, alt: $event.target.value }"
        />
      </div>
    </div>
    <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" @change="pick" />
    <p v-if="error" class="text-red-700">{{ error }}</p>
    <ImageCropper v-if="picked && ratio !== 'free'" :file="picked" :ratio="ratio" @done="upload" @cancel="picked = null" />
  </div>
</template>
