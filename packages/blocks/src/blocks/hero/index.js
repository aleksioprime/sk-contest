import { defineBlock } from '../../define.js'
import HeroBlock from './HeroBlock.vue'

export default defineBlock({
  type: 'hero',
  title: 'Обложка',
  description: 'Название, подзаголовок, даты, место и кнопка',
  component: HeroBlock,
  variants: ['image-bg', 'image-right', 'text-only'],
  variantLabels: { 'image-bg': 'Картинка фоном', 'image-right': 'Картинка справа', 'text-only': 'Только текст' },
  data: ['event.title', 'event.dates', 'event.place', 'registration.window'],
  props: {
    eyebrow: { type: 'text', label: 'Надзаголовок', inline: true, max: 80, placeholder: 'Например, «Конкурс проектов»' },
    title: { type: 'text', label: 'Заголовок', inline: true, max: 120 },
    subtitle: { type: 'text', label: 'Подзаголовок', inline: true, max: 240, multiline: true },
    image: { type: 'image', label: 'Изображение (если пусто — обложка мероприятия)', ratio: '16:9' },
    ctaLabel: { type: 'text', label: 'Текст кнопки', default: 'Подать заявку', max: 40 },
    ctaHref: { type: 'url', label: 'Ссылка кнопки (если пусто — на подачу заявки)' },
    countdown: { type: 'bool', label: 'Таймер до конца приёма заявок' },
  },
})
