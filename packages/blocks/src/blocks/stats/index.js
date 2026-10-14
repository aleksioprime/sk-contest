import { defineBlock } from '../../define.js'
import StatsBlock from './StatsBlock.vue'

export default defineBlock({
  type: 'stats',
  title: 'Цифры',
  description: '3–4 показателя с подписью',
  component: StatsBlock,
  variants: ['row', 'cards'],
  variantLabels: { row: 'В строку', cards: 'Карточки' },
  data: ['stats'],
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, max: 120 },
    source: { type: 'select', label: 'Откуда цифры', options: ['event', 'manual'], labels: { event: 'Из мероприятия: заявки, участники, направления', manual: 'Вручную' } },
    items: {
      type: 'list',
      label: 'Показатели',
      itemTitle: 'label',
      max: 4,
      item: {
        value: { type: 'text', label: 'Число', max: 20 },
        label: { type: 'text', label: 'Подпись', max: 80 },
      },
    },
  },
})
