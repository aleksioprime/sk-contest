<script setup>
/** Yandex SmartCaptcha: виджет «Я не робот». Токен уходит на сервер вместе с формой. */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({ sitekey: { type: String, required: true } })
const token = defineModel({ type: String, default: '' })

const SCRIPT = 'https://smartcaptcha.yandexcloud.net/captcha.js?render=onload&onload=__skeCaptchaReady'
const container = ref(null)
const failed = ref(false)
let widgetId = null

function loadScript() {
  if (window.smartCaptcha) return Promise.resolve()
  window.__skeCaptchaLoading ??= new Promise((resolve, reject) => {
    window.__skeCaptchaReady = resolve
    const script = document.createElement('script')
    script.src = SCRIPT
    script.defer = true
    script.onerror = reject
    document.head.append(script)
  })
  return window.__skeCaptchaLoading
}

onMounted(async () => {
  try {
    await loadScript()
    widgetId = window.smartCaptcha.render(container.value, {
      sitekey: props.sitekey,
      hl: 'ru',
      callback: (value) => (token.value = value),
    })
    window.smartCaptcha.subscribe(widgetId, 'token-expired', () => (token.value = ''))
  } catch {
    failed.value = true
  }
})

onBeforeUnmount(() => {
  if (widgetId !== null) window.smartCaptcha?.destroy(widgetId)
})

function reset() {
  token.value = ''
  if (widgetId !== null) window.smartCaptcha?.reset(widgetId)
}

defineExpose({ reset })
</script>

<template>
  <div>
    <div ref="container" class="min-h-[102px]" />
    <p v-if="failed" class="text-sm text-red-700">Не удалось загрузить проверку «Я не робот». Обновите страницу.</p>
  </div>
</template>
