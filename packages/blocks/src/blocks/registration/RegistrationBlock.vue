<script setup>
import { computed } from 'vue'
import SkbText from '../../SkbText.vue'
import { formatDateTime } from '../../format.js'

const props = defineProps({
  variant: { type: String, default: 'card' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})

const status = computed(() => {
  const { open, opensAt, closesAt } = props.data.registration
  if (open) return closesAt ? `Приём заявок открыт до ${formatDateTime(closesAt)}` : 'Приём заявок открыт'
  if (opensAt && new Date(opensAt) > new Date()) return `Приём заявок откроется ${formatDateTime(opensAt)}`
  return 'Приём заявок завершён'
})
const STEPS = [
  ['Войдите', 'по ссылке из письма — пароль не нужен'],
  ['Заполните анкету', 'черновик сохраняется, можно вернуться позже'],
  ['Отправьте заявку', 'и следите за решением в личном кабинете'],
]
</script>

<template>
  <section class="skb-registration" :class="`skb-registration--${variant}`">
    <div>
      <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
      <p class="skb-registration__status">{{ status }}</p>
      <div v-if="content.text" class="skb-richtext" v-html="content.text" />
    </div>
    <ol v-if="variant === 'steps'" class="skb-registration__steps">
      <li v-for="([title, text], index) in STEPS" :key="title">
        <span class="skb-registration__step">{{ index + 1 }}</span>
        <p><strong>{{ title }}</strong> {{ text }}</p>
      </li>
    </ol>
    <div class="skb-registration__action">
      <a v-if="data.registration.open && data.registration.url" class="skb-button skb-button--large" :href="data.registration.url">
        {{ content.buttonLabel || 'Подать заявку' }}
      </a>
    </div>
  </section>
</template>
