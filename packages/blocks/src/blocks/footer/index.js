import { defineBlock } from '../../define.js'
import FooterBlock from './FooterBlock.vue'

export default defineBlock({
  type: 'footer',
  title: 'Подвал и контакты',
  description: 'Организатор, контакты, соцсети и политика обработки данных',
  component: FooterBlock,
  variants: ['columns', 'row'],
  variantLabels: { columns: 'Колонки', row: 'Строка' },
  common: { anchor: 'contacts', menuTitle: 'Контакты', background: 'muted' },
  props: {
    organizer: { type: 'text', label: 'Организатор', inline: true, default: 'Гимназия Сколково', max: 200 },
    email: { type: 'text', label: 'Email', inline: true, max: 120 },
    phone: { type: 'text', label: 'Телефон', inline: true, max: 40 },
    address: { type: 'text', label: 'Адрес', inline: true, max: 300, multiline: true },
    socials: {
      type: 'list',
      label: 'Соцсети и ссылки',
      itemTitle: 'label',
      max: 8,
      item: {
        label: { type: 'text', label: 'Название', max: 40 },
        url: { type: 'url', label: 'Ссылка' },
      },
    },
    privacyUrl: { type: 'url', label: 'Политика обработки персональных данных' },
  },
})
