<script setup>
import { computed } from 'vue'
import { useEditor } from '../../editing.js'
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'
import { formatDateTime } from '../../format.js'

const props = defineProps({
  variant: { type: String, default: 'horizontal' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const editor = useEditor()

const items = computed(() => {
  if (props.content.source === 'manual') return props.content.items.map((item, index) => ({ ...item, path: `items.${index}` }))
  const result = []
  const { opensAt, closesAt } = props.data.registration
  if (opensAt || closesAt) {
    const date = opensAt && closesAt ? `${formatDateTime(opensAt)} — ${formatDateTime(closesAt)}` : closesAt ? `до ${formatDateTime(closesAt)}` : `с ${formatDateTime(opensAt)}`
    result.push({ date, title: 'Приём заявок' })
  }
  for (const stage of props.data.stages) {
    result.push({ date: stage.dates, title: stage.title, text: stage.kind === 'remote' ? 'Заочно' : 'Очно' })
  }
  return result
})
</script>

<template>
  <section v-if="items.length || editor" class="skb-dates" :class="`skb-dates--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
    <ol v-if="items.length" class="skb-dates__list">
      <li v-for="(item, index) in items" :key="index" class="skb-dates__item">
        <template v-if="item.path">
          <SkbText as="p" class="skb-dates__date" :path="`${item.path}.date`" :value="item.date" placeholder="Дата" />
          <SkbText as="p" class="skb-dates__title" :path="`${item.path}.title`" :value="item.title" placeholder="Событие" />
          <SkbText as="p" class="skb-dates__text" :path="`${item.path}.text`" :value="item.text" placeholder="Пояснение" />
        </template>
        <template v-else>
          <p v-if="item.date" class="skb-dates__date">{{ item.date }}</p>
          <p class="skb-dates__title">{{ item.title }}</p>
          <p v-if="item.text" class="skb-dates__text">{{ item.text }}</p>
        </template>
      </li>
    </ol>
    <SkbEmpty v-else text="Даты появятся, когда у мероприятия будут этапы или окно приёма заявок. Или выберите «Вручную»." />
  </section>
</template>
