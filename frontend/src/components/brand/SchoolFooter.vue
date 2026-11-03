<script setup>
/** Футер: продукты гимназии и ссылка на её сайт. */
import { PRODUCTS, SCHOOL, SERVICE } from '@/brand'

const year = new Date().getFullYear()
</script>

<template>
  <footer class="border-t border-line bg-surface/60 print:hidden">
    <div class="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-5 text-sm">
      <a :href="SCHOOL.url" target="_blank" rel="noopener" class="flex items-center gap-2 font-medium hover:text-brand-700">
        <img src="/gymnasium-logo.svg" alt="" class="size-6" />
        Продукты {{ SCHOOL.genitive }}
      </a>
      <nav class="flex flex-wrap gap-x-4 gap-y-1 text-ink-muted" aria-label="Продукты гимназии">
        <template v-for="product in PRODUCTS" :key="product.key">
          <span v-if="product.key === SERVICE" class="font-medium text-ink" aria-current="page">{{ product.name }}</span>
          <a v-else :href="product.url" class="hover:text-ink">{{ product.name }}</a>
        </template>
      </nav>
      <span class="text-ink-muted sm:ml-auto">
        © {{ year }} ·
        <a :href="SCHOOL.url" target="_blank" rel="noopener" class="hover:text-ink">gymnasium.sk.ru</a>
      </span>
    </div>
  </footer>
</template>
