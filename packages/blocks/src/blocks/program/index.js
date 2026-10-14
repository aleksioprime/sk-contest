import { defineBlock } from '../../define.js'
import ProgramBlock from './ProgramBlock.vue'

export default defineBlock({
  type: 'program',
  title: 'Программа',
  description: 'Расписание по дням: защиты из этапов или своя программа',
  component: ProgramBlock,
  variants: ['tabs', 'list'],
  variantLabels: { tabs: 'Вкладки по дням', list: 'Списком' },
  data: ['program'],
  common: { anchor: 'program', menuTitle: 'Программа' },
  isEmpty: (content, data) => (content.source === 'manual' ? !content.items.length : !data.program.length),
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Программа', max: 120 },
    source: { type: 'select', label: 'Откуда программа', options: ['event', 'manual'], labels: { event: 'Слоты защит этапов', manual: 'Вручную' } },
    showWorks: { type: 'bool', label: 'Показывать работы в слотах', default: true },
    items: {
      type: 'list',
      label: 'Пункты программы',
      itemTitle: 'title',
      max: 60,
      item: {
        day: { type: 'text', label: 'День', max: 40 },
        time: { type: 'text', label: 'Время', max: 40 },
        title: { type: 'text', label: 'Что происходит', max: 200 },
        place: { type: 'text', label: 'Где', max: 120 },
      },
    },
  },
})
