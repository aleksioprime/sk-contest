import { defineBlock } from '../../define.js'
import HeroBlock from './HeroBlock.vue'

export default defineBlock({
  type: 'hero',
  title: 'Обложка',
  component: HeroBlock,
  variants: ['image-bg', 'image-right', 'text-only'],
  data: ['event.title', 'event.dates', 'event.place', 'registration.window'],
  props: {
    eyebrow: { type: 'text', label: 'Надзаголовок', inline: true, max: 80 },
    title: { type: 'text', label: 'Заголовок', inline: true, max: 120 },
    subtitle: { type: 'text', label: 'Подзаголовок', inline: true, max: 240 },
    image: { type: 'image', label: 'Изображение', ratio: '16:9' },
    ctaLabel: { type: 'text', label: 'Текст кнопки', default: 'Подать заявку', max: 40 },
    ctaHref: { type: 'text', label: 'Ссылка кнопки', default: '#registration' },
    countdown: { type: 'bool', label: 'Таймер до конца приёма заявок' },
  },
})
