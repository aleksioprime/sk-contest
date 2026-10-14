<script setup>
import { useEditor } from '../../editing.js'
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'
import { assetUrl, safeHref } from '../../links.js'

defineProps({
  variant: { type: String, default: 'strip' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const editor = useEditor()
</script>

<template>
  <section v-if="content.items.length || editor" class="skb-partners" :class="`skb-partners--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
    <ul v-if="content.items.length" class="skb-partners__list">
      <li v-for="(partner, index) in content.items" :key="index" class="skb-partners__item">
        <component :is="safeHref(partner.url) ? 'a' : 'div'" :href="safeHref(partner.url) || undefined" target="_blank" rel="noopener" class="skb-partners__link">
          <img v-if="partner.logo" :src="assetUrl(data, partner.logo)" :alt="partner.name" class="skb-partners__logo" />
          <span v-else class="skb-partners__name">{{ partner.name || 'Партнёр' }}</span>
        </component>
      </li>
    </ul>
    <SkbEmpty v-else text="Добавьте логотипы партнёров в панели настроек справа." />
  </section>
</template>
