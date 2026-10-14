import { defineBlock } from '../../define.js'
import PeopleBlock from './PeopleBlock.vue'

export default defineBlock({
  type: 'people',
  title: 'Люди',
  description: 'Жюри, эксперты, организаторы',
  component: PeopleBlock,
  variants: ['grid', 'list'],
  variantLabels: { grid: 'Сетка с фото', list: 'Списком' },
  common: { anchor: 'jury' },
  isEmpty: (content) => !content.items.length,
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Жюри', max: 120 },
    items: {
      type: 'list',
      label: 'Люди',
      itemTitle: 'name',
      max: 60,
      item: {
        photo: { type: 'image', label: 'Фото', ratio: '1:1' },
        name: { type: 'text', label: 'Имя', max: 120 },
        role: { type: 'text', label: 'Должность или роль', max: 200 },
        text: { type: 'text', label: 'О человеке', max: 600, multiline: true },
      },
    },
  },
})
