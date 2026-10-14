import { defineBlock } from '../../define.js'
import PartnersBlock from './PartnersBlock.vue'

export default defineBlock({
  type: 'partners',
  title: 'Партнёры',
  description: 'Логотипы партнёров и организаторов со ссылками',
  component: PartnersBlock,
  variants: ['strip', 'grid'],
  variantLabels: { strip: 'Лента', grid: 'Сетка' },
  common: { anchor: 'partners' },
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Партнёры', max: 120 },
    items: {
      type: 'list',
      label: 'Партнёры',
      itemTitle: 'name',
      max: 40,
      item: {
        logo: { type: 'image', label: 'Логотип', ratio: 'free' },
        name: { type: 'text', label: 'Название', max: 120 },
        url: { type: 'url', label: 'Сайт' },
      },
    },
  },
})
