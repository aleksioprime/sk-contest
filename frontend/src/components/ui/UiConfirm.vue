<script setup>
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'

// Модальное окно подтверждения. Открывается через v-model:open, пояснение передаётся в слоте.
// Фокус сразу на кнопке отмены, поэтому случайное нажатие Enter ничего не подтвердит.
const props = defineProps({
  title: { type: String, required: true },
  confirmLabel: { type: String, default: 'Подтвердить' },
  variant: { type: String, default: 'primary' }, // primary | danger
  loading: { type: Boolean, default: false },
})
const open = defineModel('open', { type: Boolean, default: false })
const emit = defineEmits(['confirm'])

const id = useId()
const dialog = ref(null)

function close() {
  if (!props.loading) open.value = false
}
function onBackdropClick(event) {
  if (event.target === dialog.value) close()
}

watch(
  open,
  async (value) => {
    document.documentElement.style.overflow = value ? 'hidden' : ''
    if (!value) return
    await nextTick()
    dialog.value?.showModal?.()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  if (open.value) document.documentElement.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <dialog
      v-if="open"
      ref="dialog"
      :aria-labelledby="`${id}-title`"
      :aria-describedby="`${id}-text`"
      class="m-auto w-[calc(100%-2rem)] max-w-md rounded-card border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-ink/40"
      @cancel.prevent="close"
      @click="onBackdropClick"
    >
      <div class="grid gap-3 p-5">
        <h2 :id="`${id}-title`" class="text-lg font-semibold">{{ title }}</h2>
        <div :id="`${id}-text`" class="text-sm text-ink-muted"><slot /></div>
        <div class="mt-2 flex flex-wrap justify-end gap-2">
          <UiButton variant="secondary" :disabled="loading" @click="close">Отмена</UiButton>
          <UiButton :variant="variant" :loading="loading" @click="emit('confirm')">{{ confirmLabel }}</UiButton>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>
