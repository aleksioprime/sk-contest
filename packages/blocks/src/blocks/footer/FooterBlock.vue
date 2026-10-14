<script setup>
import SkbText from '../../SkbText.vue'
import { safeHref } from '../../links.js'

defineProps({
  variant: { type: String, default: 'columns' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const year = new Date().getFullYear()
</script>

<template>
  <footer class="skb-footer" :class="`skb-footer--${variant}`">
    <div>
      <SkbText as="p" class="skb-footer__org" path="organizer" :value="content.organizer" placeholder="Организатор" />
      <p class="skb-footer__muted">© {{ year }} · {{ data.event.title }}</p>
    </div>
    <div class="skb-footer__contacts">
      <a v-if="content.email && !data.editing" :href="`mailto:${content.email}`">{{ content.email }}</a>
      <SkbText v-else as="p" path="email" :value="content.email" placeholder="email@example.ru" />
      <a v-if="content.phone && !data.editing" :href="`tel:${content.phone.replace(/[^+\d]/g, '')}`">{{ content.phone }}</a>
      <SkbText v-else as="p" path="phone" :value="content.phone" placeholder="+7 (000) 000-00-00" />
      <SkbText as="p" class="skb-footer__muted" path="address" :value="content.address" placeholder="Адрес" multiline />
    </div>
    <div class="skb-footer__links">
      <template v-for="(link, index) in content.socials" :key="index">
        <a v-if="safeHref(link.url)" :href="safeHref(link.url)" target="_blank" rel="noopener">{{ link.label || link.url }}</a>
      </template>
      <a v-if="safeHref(content.privacyUrl)" :href="safeHref(content.privacyUrl)" class="skb-footer__muted" target="_blank" rel="noopener">
        Политика обработки персональных данных
      </a>
    </div>
  </footer>
</template>
