<script setup>
import { SitePage, themeFontsHref } from '@sk-events/blocks'

const { site } = await useSite()
const config = useRuntimeConfig()

if (site) {
  useSeoMeta({
    title: site.seo.title,
    description: site.seo.description,
    ogTitle: site.seo.title,
    ogDescription: site.seo.description,
    ogImage: site.seo.image || undefined,
    ogType: 'website',
    ogUrl: site.canonical,
    twitterCard: site.seo.image ? 'summary_large_image' : 'summary',
  })
  useHead({
    link: [
      { rel: 'canonical', href: site.canonical },
      { rel: 'stylesheet', href: themeFontsHref(site.theme) },
      ...(site.seo.favicon ? [{ rel: 'icon', href: site.seo.favicon }] : []),
    ],
    meta: [{ name: 'theme-color', content: site.theme.accent || '#534ab7' }],
    script: site.seo.metrika ? [{ key: 'metrika', innerHTML: metrikaCode(site.seo.metrika) }] : [],
  })
} else {
  useSeoMeta({ title: 'SK Events', description: 'Мероприятия Гимназии Сколково' })
}

/** Счётчик Яндекс.Метрики: номер счётчика проверен на сервере (только цифры). */
function metrikaCode(id) {
  const counter = String(id).replace(/\D/g, '')
  return `(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");ym(${counter},"init",{clickmap:true,trackLinks:true,accurateTrackBounce:true});`
}
</script>

<template>
  <SitePage v-if="site" :page="site.page" :theme="site.theme" :data="site.data" :phase="site.phase" />
  <main v-else class="root">
    <h1>SK Events</h1>
    <p>Мероприятия Гимназии Сколково.</p>
    <a :href="config.public.appUrl">Перейти в кабинет</a>
  </main>
</template>

<style scoped>
.root {
  font-family: 'Golos Text', system-ui, sans-serif;
  max-width: 640px;
  margin: 20vh auto;
  padding: 0 20px;
}
</style>
