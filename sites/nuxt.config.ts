export default defineNuxtConfig({
  compatibilityDate: '2026-09-01',
  devtools: { enabled: false },
  css: ['@sk-events/blocks/styles.css'],
  build: { transpile: ['@sk-events/blocks'] },
  runtimeConfig: {
    // Адрес API внутри сети контейнеров: NUXT_API_INTERNAL_URL
    apiInternalUrl: 'http://localhost:8000',
    public: {
      // Базовый домен лендингов: NUXT_PUBLIC_SITES_BASE_DOMAIN
      sitesBaseDomain: 'events.skolhub.ru',
      appUrl: 'http://localhost:8501',
    },
  },
  app: {
    head: {
      htmlAttrs: { lang: 'ru' },
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
      // Шрифты темы подключает страница сайта (themeFontsHref)
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
      ],
    },
  },
})
