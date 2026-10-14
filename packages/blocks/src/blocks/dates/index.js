import { defineBlock } from '../../define.js'
import DatesBlock from './DatesBlock.vue'

export default defineBlock({
  type: 'dates',
  title: 'Ключевые даты',
  description: 'Приём заявок, этапы и финал',
  component: DatesBlock,
  variants: ['horizontal', 'vertical'],
  variantLabels: { horizontal: 'В строку', vertical: 'Столбиком' },
  data: ['registration.window', 'stages'],
  common: { anchor: 'dates', menuTitle: 'Даты' },
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Ключевые даты', max: 120 },
    source: { type: 'select', label: 'Откуда даты', options: ['event', 'manual'], labels: { event: 'Из этапов мероприятия', manual: 'Вручную' } },
    items: {
      type: 'list',
      label: 'Даты',
      itemTitle: 'title',
      max: 12,
      item: {
        date: { type: 'text', label: 'Дата', max: 60 },
        title: { type: 'text', label: 'Событие', max: 120 },
        text: { type: 'text', label: 'Пояснение', max: 300 },
      },
    },
  },
})
