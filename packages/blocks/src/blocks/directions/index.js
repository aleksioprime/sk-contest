import { defineBlock } from '../../define.js'
import DirectionsBlock from './DirectionsBlock.vue'

export default defineBlock({
  type: 'directions',
  title: 'Направления',
  description: 'Направления или номинации мероприятия',
  component: DirectionsBlock,
  variants: ['cards', 'chips'],
  variantLabels: { cards: 'Карточки', chips: 'Плашки' },
  data: ['directions'],
  common: { anchor: 'directions', menuTitle: 'Направления', background: 'muted' },
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Направления', max: 120 },
    intro: { type: 'text', label: 'Вступление', inline: true, max: 500, multiline: true },
  },
})
