import { createPinia } from 'pinia'
import { createApp } from 'vue'
import { skUi } from 'sk-ui'
import App from './App.vue'
import { SERVICE_NAME } from './brand'
import { router } from './router'
import './styles/main.css'

createApp(App).use(createPinia()).use(router).use(skUi, { serviceName: SERVICE_NAME }).mount('#app')
