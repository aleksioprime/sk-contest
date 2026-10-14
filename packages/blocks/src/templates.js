/**
 * Шаблоны лендингов под типы мероприятий: набор и порядок блоков, тема.
 * Блоки с данными (даты, направления, итоги) заполняются из мероприятия сами.
 */
import { getBlock } from './registry.js'
import { createBlockInstance } from './schema.js'
import { DEFAULT_THEME, THEME_PRESETS } from './theme.js'

const BASE = ['header', 'hero', 'text', 'dates', 'directions', 'registration', 'results', 'faq', 'footer']

export const TEMPLATES = Object.freeze({
  project_contest: {
    title: 'Конкурс проектов',
    preset: 'violet',
    blocks: ['header', 'hero', 'stats', 'text', 'dates', 'directions', 'registration', 'program', 'people', 'results', 'documents', 'faq', 'partners', 'footer'],
  },
  conference: {
    title: 'Конференция',
    preset: 'ocean',
    blocks: ['header', 'hero', 'text', 'directions', 'dates', 'program', 'people', 'registration', 'results', 'documents', 'gallery', 'footer'],
  },
  creative: {
    title: 'Творческий конкурс',
    preset: 'classic',
    blocks: ['header', 'hero', 'text', 'directions', 'dates', 'registration', 'people', 'gallery', 'results', 'faq', 'footer'],
  },
  open_event: {
    title: 'Открытое мероприятие',
    preset: 'emerald',
    blocks: ['header', 'hero', 'text', 'program', 'registration', 'gallery', 'faq', 'partners', 'footer'],
  },
  selection: {
    title: 'Отбор',
    preset: 'violet',
    blocks: ['header', 'hero', 'text', 'dates', 'directions', 'registration', 'documents', 'results', 'faq', 'footer'],
  },
})

let counter = 0

/** Уникальный id блока внутри сайта. */
export function newBlockId() {
  counter = (counter + 1) % 1e6
  return `b${Date.now().toString(36)}${counter.toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

/** Блоки, которые заполняются из мероприятия и не показывают образцы текста. */
const DATA_BLOCKS = new Set(['header', 'hero', 'text', 'dates', 'directions', 'stats', 'program', 'registration', 'results', 'footer'])

/**
 * Черновик сайта по шаблону типа мероприятия.
 * dataOnly — сайт до первой публикации: только блоки с настоящими данными, без образцов.
 */
export function buildTemplate(eventType, event = {}, { dataOnly = false, stableIds = dataOnly } = {}) {
  const template = TEMPLATES[eventType] ?? { preset: 'violet', blocks: BASE }
  const types = template.blocks.filter((type) => !dataOnly || (DATA_BLOCKS.has(type) && (type !== 'text' || event.description)))
  // Стабильные id нужны, когда шаблон собирается и на сервере, и в браузере
  const blocks = types.map((type, index) => {
    const block = createBlockInstance(getBlock(type), stableIds ? `t${index}-${type}` : newBlockId())
    if (type === 'text') {
      block.props.title = 'О мероприятии'
      block.props.body = event.description ? descriptionHtml(event.description) : ''
    }
    return block
  })
  const preset = THEME_PRESETS[template.preset]
  return {
    theme: { ...DEFAULT_THEME, preset: template.preset, accent: preset.accent, fontPair: preset.fontPair, radius: preset.radius },
    pages: [{ path: '', title: 'Главная', blocks }],
    seo: { title: '', description: '', image: null, metrika: '' },
  }
}

function descriptionHtml(text) {
  const escape = (s) => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => `<p>${escape(p).replaceAll('\n', '<br>')}</p>`)
    .join('')
}
