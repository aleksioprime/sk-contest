import { defineBlock } from '../../define.js'
import RegistrationBlock from './RegistrationBlock.vue'

export default defineBlock({
  type: 'registration',
  title: 'Регистрация',
  description: 'Статус приёма заявок и кнопка подачи. Меняется сам по датам приёма',
  component: RegistrationBlock,
  variants: ['card', 'steps'],
  variantLabels: { card: 'Карточка с кнопкой', steps: 'Шаги подачи' },
  data: ['registration'],
  common: { anchor: 'registration', menuTitle: 'Регистрация', background: 'accent' },
  props: {
    title: { type: 'text', label: 'Заголовок', inline: true, default: 'Регистрация', max: 120 },
    text: { type: 'richtext', label: 'Условия участия' },
    buttonLabel: { type: 'text', label: 'Текст кнопки', default: 'Подать заявку', max: 40 },
  },
})
