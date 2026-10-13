import { defineBlock } from '../../define.js'
import TextBlock from './TextBlock.vue'

export default defineBlock({
  type: 'text',
  title: 'Текст',
  component: TextBlock,
  variants: ['single', 'with-image', 'two-columns'],
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, max: 120 },
    body: { type: 'richtext', label: 'Текст' },
    image: { type: 'image', label: 'Фото', ratio: '4:3' },
  },
})
