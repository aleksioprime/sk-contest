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
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&family=Unbounded:wght@500;700&display=swap',
        },
      ],
    },
  },
})
