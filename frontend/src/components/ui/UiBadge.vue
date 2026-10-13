<script setup>
const props = defineProps({
  tone: { type: String, default: 'neutral' }, // neutral | brand | success | warning | danger | score
})

const tones = {
  neutral: 'bg-canvas text-ink-muted border border-line',
  brand: 'bg-brand-100 text-brand-700',
  success: 'bg-green-100 text-green-800',
  warning: 'bg-amber-100 text-amber-800',
  danger: 'bg-red-100 text-red-800',
  score: 'bg-score-100 text-score-600',
}
</script>

<template>
  <span class="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold" :class="tones[props.tone]">
    <slot />
  </span>
</template>
