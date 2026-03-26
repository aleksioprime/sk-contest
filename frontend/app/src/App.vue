<script setup>
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'

const route = useRoute()
</script>

<template>
  <AppHeader v-if="route.name !== 'login'" />
  <main class="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
    <router-view />
  </main>
</template>
