import { defineBlock } from '../../define.js'
import FaqBlock from './FaqBlock.vue'

export default defineBlock({
  type: 'faq',
  title: 'Вопросы и ответы',
  description: 'Раскрывающийся список частых вопросов',
  component: FaqBlock,
  common: { anchor: 'faq', menuTitle: 'Вопросы' },
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Вопросы и ответы', max: 120 },
    items: {
      type: 'list',
      label: 'Вопросы',
      itemTitle: 'question',
      max: 60,
      default: [
        { question: 'Кто может участвовать?', answer: 'Опишите, кто может подать заявку.' },
        { question: 'Сколько стоит участие?', answer: 'Участие бесплатное.' },
      ],
      item: {
        question: { type: 'text', label: 'Вопрос', max: 300 },
        answer: { type: 'text', label: 'Ответ', max: 3000, multiline: true },
      },
    },
  },
})
