import { defineBlock } from '../../define.js'
import ResultsBlock from './ResultsBlock.vue'

export default defineBlock({
  type: 'results',
  title: 'Результаты',
  description: 'Победители и призёры по направлениям. Скрыт, пока итоги не опубликованы',
  component: ResultsBlock,
  variants: ['cards', 'table'],
  variantLabels: { cards: 'Карточки', table: 'Таблица' },
  data: ['results'],
  common: { anchor: 'results', menuTitle: 'Итоги' },
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Победители и призёры', max: 120 },
    intro: { type: 'text', label: 'Вступление', inline: true, max: 500, multiline: true },
  },
})
