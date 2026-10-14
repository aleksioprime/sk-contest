import { defineBlock } from '../../define.js'
import GalleryBlock from './GalleryBlock.vue'

export default defineBlock({
  type: 'gallery',
  title: 'Галерея',
  description: 'Фото с подписями и просмотром на весь экран',
  component: GalleryBlock,
  variants: ['grid', 'strip'],
  variantLabels: { grid: 'Сетка', strip: 'Лента' },
  common: { anchor: 'gallery', menuTitle: 'Фото' },
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Фотографии', max: 120 },
    items: {
      type: 'list',
      label: 'Фото',
      itemTitle: 'caption',
      max: 80,
      item: {
        image: { type: 'image', label: 'Фото', ratio: '4:3' },
        caption: { type: 'text', label: 'Подпись', max: 200 },
      },
    },
  },
})
