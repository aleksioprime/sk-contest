<script setup>
const props = defineProps({
  variant: { type: String, default: 'secondary' }, // primary | secondary | ghost | danger
  size: { type: String, default: 'md' }, // sm | md
  type: { type: String, default: 'button' },
  loading: { type: Boolean, default: false },
})

const variants = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700',
  secondary: 'bg-surface text-ink border border-line hover:bg-brand-50',
  ghost: 'text-ink hover:bg-brand-50',
  danger: 'bg-red-600 text-white hover:bg-red-700',
}
const sizes = { sm: 'h-8 px-3 text-sm', md: 'h-10 px-4' }
</script>

<template>
  <button
    :type="type"
    :aria-busy="loading || undefined"
    class="inline-flex items-center justify-center gap-2 rounded-control font-medium transition-colors disabled:opacity-60"
    :class="[variants[props.variant], sizes[props.size]]"
  >
    <span v-if="loading" class="size-4 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden="true" />
    <slot />
  </button>
</template>
