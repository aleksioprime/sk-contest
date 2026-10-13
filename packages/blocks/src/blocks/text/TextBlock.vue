<script setup>
defineProps({
  variant: { type: String, default: 'single' },
  props: { type: Object, required: true },
  event: { type: Object, default: () => ({}) },
})
</script>

<template>
  <section class="skb-text" :class="`skb-text--${variant}`">
    <h2 v-if="props.title" class="skb-title">{{ props.title }}</h2>
    <!-- HTML приходит только из Tiptap и очищается на сервере перед сохранением -->
    <div class="skb-text__content" v-html="props.body" />
    <img v-if="props.image?.url && variant === 'with-image'" class="skb-text__image" :src="props.image.url" :alt="props.image.alt || ''" />
  </section>
</template>
