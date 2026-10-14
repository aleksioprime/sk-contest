<script setup>
/**
 * Меню без прокрутки: пункты, которые не помещаются по ширине, уходят в выпадающее «Ещё».
 * Ширины пунктов измеряются в скрытом ряду, раскладка пересчитывается при изменении размера.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const props = defineProps({ links: { type: Array, required: true } })
const route = useRoute()

const nav = ref(null)
const measure = ref(null)
const moreButton = ref(null)
const visibleCount = ref(props.links.length)
const open = ref(false)
const GAP = 4

const visible = computed(() => props.links.slice(0, visibleCount.value))
const hidden = computed(() => props.links.slice(visibleCount.value))
const hiddenActive = computed(() => hidden.value.some((link) => route.matched.some((r) => r.name === link.to.name)))

function layout() {
  if (!nav.value || !measure.value) return
  const widths = [...measure.value.children].map((el) => el.offsetWidth)
  const available = nav.value.clientWidth
  const total = widths.reduce((sum, w) => sum + w + GAP, 0)
  if (total <= available) {
    visibleCount.value = widths.length
    return
  }
  const moreWidth = (moreButton.value?.offsetWidth || 72) + GAP
  let used = 0
  let count = 0
  for (const width of widths) {
    if (used + width + GAP + moreWidth > available) break
    used += width + GAP
    count += 1
  }
  visibleCount.value = count
}

function onDocumentClick(event) {
  if (open.value && !event.target.closest('[data-overflow-more]')) open.value = false
}

function onKey(event) {
  if (event.key === 'Escape') open.value = false
}

let observer
onMounted(() => {
  observer = new ResizeObserver(layout)
  observer.observe(nav.value)
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKey)
  nextTick(layout)
})
onBeforeUnmount(() => {
  observer?.disconnect()
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKey)
})
watch(() => props.links.map((l) => l.label).join(), () => nextTick(layout))
watch(() => route.fullPath, () => (open.value = false))

const linkClass = 'whitespace-nowrap rounded-control px-3 py-1.5 text-ink-muted hover:bg-brand-50 hover:text-ink'
</script>

<template>
  <nav ref="nav" class="relative flex min-w-0 flex-1 items-center gap-1 text-sm" aria-label="Основное меню">
    <RouterLink v-for="link in visible" :key="link.label" :to="link.to" :class="linkClass" active-class="!bg-brand-100 !text-brand-700">
      {{ link.label }}
    </RouterLink>

    <div v-if="hidden.length" class="relative" data-overflow-more>
      <button
        ref="moreButton"
        type="button"
        :class="[linkClass, { '!bg-brand-100 !text-brand-700': hiddenActive }]"
        aria-haspopup="menu"
        :aria-expanded="open"
        @click="open = !open"
      >
        Ещё ▾
      </button>
      <div v-if="open" role="menu" class="absolute left-0 top-full z-20 mt-1 grid min-w-48 gap-0.5 rounded-card border border-line bg-surface p-1 shadow-lg">
        <RouterLink
          v-for="link in hidden"
          :key="link.label"
          :to="link.to"
          role="menuitem"
          class="rounded-control px-3 py-2 text-ink hover:bg-brand-50"
          active-class="!bg-brand-100 !text-brand-700"
        >
          {{ link.label }}
        </RouterLink>
      </div>
    </div>

    <!-- Скрытый ряд для измерения ширины пунктов -->
    <div ref="measure" class="pointer-events-none invisible absolute left-0 top-0 flex gap-1" aria-hidden="true">
      <span v-for="link in links" :key="link.label" :class="linkClass">{{ link.label }}</span>
    </div>
  </nav>
</template>
