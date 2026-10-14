import { defineBlock } from '../../define.js'
import HeaderBlock from './HeaderBlock.vue'

export default defineBlock({
  type: 'header',
  title: 'Шапка',
  description: 'Логотип, меню по разделам страницы и кнопка заявки',
  component: HeaderBlock,
  variants: ['sticky', 'overlay'],
  variantLabels: { sticky: 'Закреплённая сверху', overlay: 'Поверх обложки' },
  props: {
    logo: { type: 'image', label: 'Логотип', ratio: 'free' },
    title: { type: 'text', label: 'Название', inline: true, max: 80, placeholder: 'Название мероприятия' },
    showCta: { type: 'bool', label: 'Кнопка «Подать заявку» во время приёма', default: true },
    ctaLabel: { type: 'text', label: 'Текст кнопки', default: 'Подать заявку', max: 40 },
  },
})
