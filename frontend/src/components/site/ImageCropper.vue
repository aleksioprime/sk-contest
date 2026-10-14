<script setup>
/**
 * Кадрирование картинки под пропорции блока: перетаскивание и масштаб.
 * Результат — JPEG не шире 2000 px, чтобы лендинг не грузил лишнего.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({
  file: { type: File, required: true },
  ratio: { type: String, default: '16:9' }, // «16:9», «1:1» или free
})
const emit = defineEmits(['done', 'cancel'])

const FRAME_WIDTH = 480
const MAX_OUTPUT = 2000
const aspect = computed(() => {
  const [w, h] = props.ratio.split(':').map(Number)
  return w && h ? w / h : null
})

const url = URL.createObjectURL(props.file)
const image = ref(null)
const natural = ref({ width: 1, height: 1 })
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const frame = computed(() => {
  const ratio = aspect.value ?? natural.value.width / natural.value.height
  return { width: FRAME_WIDTH, height: Math.round(FRAME_WIDTH / ratio) }
})
// Масштаб, при котором картинка закрывает рамку целиком
const cover = computed(() => Math.max(frame.value.width / natural.value.width, frame.value.height / natural.value.height))
const scale = computed(() => cover.value * zoom.value)

function clamp() {
  const w = natural.value.width * scale.value
  const h = natural.value.height * scale.value
  offset.value = {
    x: Math.min(0, Math.max(frame.value.width - w, offset.value.x)),
    y: Math.min(0, Math.max(frame.value.height - h, offset.value.y)),
  }
}

function loaded() {
  natural.value = { width: image.value.naturalWidth, height: image.value.naturalHeight }
  offset.value = {
    x: (frame.value.width - natural.value.width * scale.value) / 2,
    y: (frame.value.height - natural.value.height * scale.value) / 2,
  }
}

let drag = null
function start(event) {
  drag = { x: event.clientX - offset.value.x, y: event.clientY - offset.value.y }
  event.target.setPointerCapture(event.pointerId)
}
function move(event) {
  if (!drag) return
  offset.value = { x: event.clientX - drag.x, y: event.clientY - drag.y }
  clamp()
}
function end() {
  drag = null
}
function setZoom(value) {
  const center = { x: frame.value.width / 2, y: frame.value.height / 2 }
  const before = scale.value
  zoom.value = value
  const k = scale.value / before
  offset.value = { x: center.x - (center.x - offset.value.x) * k, y: center.y - (center.y - offset.value.y) * k }
  clamp()
}

function save() {
  const sourceWidth = frame.value.width / scale.value
  const sourceHeight = frame.value.height / scale.value
  const outputWidth = Math.min(MAX_OUTPUT, Math.round(sourceWidth))
  const canvas = document.createElement('canvas')
  canvas.width = outputWidth
  canvas.height = Math.round(outputWidth * (frame.value.height / frame.value.width))
  canvas.getContext('2d').drawImage(
    image.value,
    -offset.value.x / scale.value,
    -offset.value.y / scale.value,
    sourceWidth,
    sourceHeight,
    0,
    0,
    canvas.width,
    canvas.height,
  )
  canvas.toBlob((blob) => emit('done', blob), 'image/jpeg', 0.88)
}

function keydown(event) {
  if (event.key === 'Escape') emit('cancel')
}
onMounted(() => window.addEventListener('keydown', keydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', keydown)
  URL.revokeObjectURL(url)
})
</script>

<template>
  <div class="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label="Кадрирование">
    <div class="grid w-full max-w-[528px] gap-4 rounded-card bg-surface p-6 shadow-xl">
      <p class="font-semibold">Кадрирование {{ aspect ? `(${ratio})` : '' }}</p>
      <div
        class="relative mx-auto cursor-move touch-none overflow-hidden rounded-control bg-canvas"
        :style="{ width: `${frame.width}px`, height: `${frame.height}px`, maxWidth: '100%' }"
        @pointerdown="start"
        @pointermove="move"
        @pointerup="end"
        @pointercancel="end"
      >
        <img
          ref="image"
          :src="url"
          alt=""
          draggable="false"
          class="pointer-events-none absolute top-0 left-0 max-w-none origin-top-left select-none"
          :style="{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})` }"
          @load="loaded"
        />
      </div>
      <label class="flex items-center gap-3 text-sm">
        Масштаб
        <input type="range" min="1" max="4" step="0.01" :value="zoom" class="flex-1 accent-brand-600" @input="setZoom(Number($event.target.value))" />
      </label>
      <p class="text-xs text-ink-muted">Перетащите картинку, чтобы выбрать видимую часть.</p>
      <div class="flex justify-end gap-2">
        <UiButton variant="ghost" @click="emit('cancel')">Отмена</UiButton>
        <UiButton variant="primary" @click="save">Готово</UiButton>
      </div>
    </div>
  </div>
</template>
