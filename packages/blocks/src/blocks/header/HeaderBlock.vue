<script setup>
import { computed } from 'vue'
import SkbText from '../../SkbText.vue'
import { assetUrl } from '../../links.js'

const props = defineProps({
  variant: { type: String, default: 'sticky' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const logo = computed(() => assetUrl(props.data, props.content.logo))
</script>

<template>
  <header class="skb-header" :class="`skb-header--${variant}`">
    <a class="skb-header__brand" href="#">
      <img v-if="logo" :src="logo" :alt="content.logo?.alt || ''" class="skb-header__logo" />
      <SkbText as="span" path="title" :value="content.title" :fallback="data.event.title" />
    </a>
    <nav v-if="data.menu.length" class="skb-header__nav" aria-label="Разделы">
      <a v-for="item in data.menu" :key="item.anchor" :href="`#${item.anchor}`">{{ item.title }}</a>
    </nav>
    <details v-if="data.menu.length" class="skb-header__burger">
      <summary aria-label="Меню">Меню</summary>
      <nav>
        <a v-for="item in data.menu" :key="item.anchor" :href="`#${item.anchor}`">{{ item.title }}</a>
      </nav>
    </details>
    <a v-if="content.showCta && data.registration.open && content.ctaLabel" class="skb-button skb-button--small" :href="data.registration.url">
      {{ content.ctaLabel }}
    </a>
  </header>
</template>
