<script setup>
import { SitePage } from '@sk-events/blocks'

const { site } = await useSite()
const config = useRuntimeConfig()

useSeoMeta({
  title: site ? site.title : 'SK Events',
  description: site ? site.description : 'Мероприятия Гимназии Сколково',
  ogTitle: site ? site.title : 'SK Events',
})
</script>

<template>
  <SitePage v-if="site" :page="site.page" :theme="site.theme" :event="site.event" phase="registration" />
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
