<script setup>
import { computed } from 'vue'
import { useEditor } from '../../editing.js'
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'

const props = defineProps({
  variant: { type: String, default: 'row' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})

function plural(n, forms) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return forms[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1]
  return forms[2]
}

const editor = useEditor()

const FROM_EVENT = [
  ['applications', ['заявка', 'заявки', 'заявок']],
  ['participants', ['участник', 'участника', 'участников']],
  ['directions', ['направление', 'направления', 'направлений']],
  ['stages', ['этап', 'этапа', 'этапов']],
]

const items = computed(() => {
  if (props.content.source !== 'event') return props.content.items.map((item, index) => ({ ...item, path: `items.${index}` }))
  return FROM_EVENT.filter(([key]) => props.data.stats[key]).map(([key, forms]) => ({
    value: String(props.data.stats[key]),
    label: plural(props.data.stats[key], forms),
  }))
})
</script>

<template>
  <section v-if="items.length || editor" class="skb-stats" :class="`skb-stats--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" placeholder="Заголовок (необязательно)" />
    <ul class="skb-stats__list">
      <li v-for="(item, index) in items" :key="index" class="skb-stats__item">
        <template v-if="item.path">
          <SkbText as="p" class="skb-stats__value" :path="`${item.path}.value`" :value="item.value" placeholder="100" />
          <SkbText as="p" class="skb-stats__label" :path="`${item.path}.label`" :value="item.label" placeholder="подпись" />
        </template>
        <template v-else>
          <p class="skb-stats__value">{{ item.value }}</p>
          <p class="skb-stats__label">{{ item.label }}</p>
        </template>
      </li>
    </ul>
    <SkbEmpty v-if="!items.length" :text="content.source === 'event' ? 'Цифры появятся, когда будут заявки. Или выберите «Вручную».' : 'Добавьте показатели в панели настроек справа.'" />
  </section>
</template>
