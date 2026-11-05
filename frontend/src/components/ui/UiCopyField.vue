<script setup>
/** Адрес только для чтения с кнопкой копирования. */
import { ref } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({
  value: { type: String, required: true },
  label: { type: String, default: 'Адрес' },
})
const copied = ref(false)

async function copy() {
  await navigator.clipboard?.writeText(props.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}
</script>

<template>
  <div class="flex items-center gap-2">
    <input :value="value" readonly :aria-label="label" class="h-10 min-w-0 flex-1 rounded-control border border-line bg-canvas px-3 text-sm" @focus="$event.target.select()" />
    <UiButton size="sm" @click="copy">{{ copied ? 'Скопировано' : 'Скопировать' }}</UiButton>
  </div>
</template>
