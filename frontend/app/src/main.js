/**
 * Точка входа приложения «Жюри SK».
 * Инициализирует Vue-приложение с подключением хранилища Pinia и маршрутизатора.
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())  // Глобальное хранилище состояния (авторизация, роли)
app.use(router)         // Маршрутизация с навигационными гардами
app.mount('#app')
