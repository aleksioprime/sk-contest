<script setup>
import { SitePage } from '@sk-events/blocks'

const { target, site } = useSite()
const config = useRuntimeConfig()

if (target.kind === 'unknown') {
  throw createError({ statusCode: 404, statusMessage: 'Сайт не найден' })
}

useSeoMeta({
  title: site ? site.title : 'SK Events',
  description: site ? undefined : 'Мероприятия Гимназии Сколково',
})
</script>

<template>
  <SitePage v-if="site" :page="site.page" :theme="site.theme" :event="site.event" />
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
