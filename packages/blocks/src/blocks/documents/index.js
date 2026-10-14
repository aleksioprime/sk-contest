import { defineBlock } from '../../define.js'
import DocumentsBlock from './DocumentsBlock.vue'

export default defineBlock({
  type: 'documents',
  title: 'Документы',
  description: 'Положение, шаблоны, памятки для скачивания',
  component: DocumentsBlock,
  variants: ['list', 'cards'],
  variantLabels: { list: 'Списком', cards: 'Карточки' },
  common: { anchor: 'documents' },
  isEmpty: (content) => !content.items.length,
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Документы', max: 120 },
    items: {
      type: 'list',
      label: 'Документы',
      itemTitle: 'title',
      max: 40,
      item: {
        title: { type: 'text', label: 'Название', max: 200 },
        file: { type: 'file', label: 'Файл' },
        note: { type: 'text', label: 'Пояснение', max: 300 },
      },
    },
  },
})
