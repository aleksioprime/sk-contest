<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import SkbText from '../../SkbText.vue'
import { assetUrl, safeHref } from '../../links.js'

const props = defineProps({
  variant: { type: String, default: 'image-bg' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})

const meta = computed(() => [props.data.event.dates, props.data.event.place].filter(Boolean).join(' · '))
const image = computed(() => (props.variant === 'text-only' ? '' : assetUrl(props.data, props.content.image || props.data.event.cover)))
const href = computed(() => safeHref(props.content.ctaHref) || (props.data.registration.open ? props.data.registration.url : ''))

const now = ref(Date.now())
let timer
onMounted(() => (timer = setInterval(() => (now.value = Date.now()), 60000)))
onBeforeUnmount(() => clearInterval(timer))

const countdown = computed(() => {
  const closes = props.data.registration.closesAt
  if (!props.content.countdown || !props.data.registration.open || !closes) return ''
  const minutes = Math.floor((new Date(closes).getTime() - now.value) / 60000)
  if (minutes <= 0) return ''
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  return days ? `${days} дн. ${hours} ч.` : `${hours} ч. ${minutes % 60} мин.`
})
</script>

<template>
  <section class="skb-hero" :class="[`skb-hero--${variant}`, { 'skb-hero--has-image': image }]">
    <img v-if="image && variant === 'image-bg'" class="skb-hero__bg" :src="image" alt="" />
    <div class="skb-hero__body">
      <SkbText as="p" class="skb-hero__eyebrow" path="eyebrow" :value="content.eyebrow" placeholder="Надзаголовок" />
      <SkbText as="h1" class="skb-hero__title" path="title" :value="content.title" :fallback="data.event.title" />
      <SkbText as="p" class="skb-hero__subtitle" path="subtitle" :value="content.subtitle" :fallback="data.event.shortDescription" multiline />
      <p v-if="meta" class="skb-hero__meta">{{ meta }}</p>
      <div class="skb-hero__actions">
        <a v-if="href && content.ctaLabel" class="skb-button" :href="href">{{ content.ctaLabel }}</a>
        <p v-if="countdown" class="skb-hero__countdown">До конца приёма заявок: <strong>{{ countdown }}</strong></p>
      </div>
    </div>
    <img v-if="image && variant === 'image-right'" class="skb-hero__image" :src="image" :alt="content.image?.alt || ''" />
  </section>
</template>
