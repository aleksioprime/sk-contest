<script setup>
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'
import { assetUrl } from '../../links.js'

defineProps({
  variant: { type: String, default: 'single' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
</script>

<template>
  <section class="skb-text" :class="`skb-text--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" placeholder="Заголовок" />
    <div class="skb-text__grid">
      <!-- HTML приходит только из редактора и очищается на сервере перед сохранением -->
      <div v-if="content.body" class="skb-richtext skb-text__content" v-html="content.body" />
      <SkbEmpty v-else text="Текст правится в панели настроек справа." />
      <img v-if="content.image && variant === 'with-image'" class="skb-text__image" :src="assetUrl(data, content.image)" :alt="content.image.alt || ''" />
    </div>
  </section>
</template>
