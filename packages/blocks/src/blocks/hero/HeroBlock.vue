<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'image-bg' },
  props: { type: Object, required: true },
  event: { type: Object, default: () => ({}) },
})

const p = computed(() => props.props)
const dates = computed(() => [props.event.dates, props.event.place].filter(Boolean).join(' · '))
</script>

<template>
  <section class="skb-hero" :class="`skb-hero--${variant}`">
    <div class="skb-hero__body">
      <p v-if="p.eyebrow" class="skb-hero__eyebrow">{{ p.eyebrow }}</p>
      <h1 class="skb-hero__title">{{ p.title || event.title }}</h1>
      <p v-if="p.subtitle" class="skb-hero__subtitle">{{ p.subtitle }}</p>
      <p v-if="dates" class="skb-hero__meta">{{ dates }}</p>
      <a v-if="p.ctaLabel" class="skb-button" :href="p.ctaHref || '#registration'">{{ p.ctaLabel }}</a>
    </div>
    <img v-if="p.image?.url && variant !== 'text-only'" class="skb-hero__image" :src="p.image.url" :alt="p.image.alt || ''" />
  </section>
</template>
