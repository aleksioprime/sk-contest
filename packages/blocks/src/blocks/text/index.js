import { defineBlock } from '../../define.js'
import TextBlock from './TextBlock.vue'

export default defineBlock({
  type: 'text',
  title: 'Текст',
  description: 'Форматированный текст и фото',
  component: TextBlock,
  variants: ['single', 'with-image', 'two-columns'],
  variantLabels: { single: 'Колонка', 'with-image': 'Текст и фото', 'two-columns': 'Две колонки' },
  common: { anchor: 'about', menuTitle: 'О мероприятии' },
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, max: 120 },
    body: { type: 'richtext', label: 'Текст' },
    image: { type: 'image', label: 'Фото', ratio: '4:3' },
  },
})
