/**
 * Описание блока лендинга.
 *
 * Одна схема используется в трёх местах: редактор строит по ней форму настроек,
 * backend проверяет props перед сохранением (JSON Schema из toJsonSchema выгружается в backend),
 * а sites и превью в редакторе рендерят компонент.
 */

export const PROP_TYPES = ['text', 'richtext', 'url', 'image', 'file', 'bool', 'select', 'list']

export const COMMON_DEFAULTS = Object.freeze({
  anchor: '',
  menuTitle: '', // пункт меню в шапке; пусто — блока в меню нет
  background: 'default', // default | muted | accent
  visibility: 'always', // always | registration | results
})

export const BACKGROUNDS = { default: 'Обычный', muted: 'Приглушённый', accent: 'Акцентный' }
export const VISIBILITY = {
  always: 'Всегда',
  registration: 'Только во время приёма заявок',
  results: 'Только после публикации итогов',
}

function checkProps(type, props, path = '') {
  for (const [name, prop] of Object.entries(props)) {
    const where = `${path}${name}`
    if (!PROP_TYPES.includes(prop.type)) {
      throw new Error(`Блок ${type}: у поля ${where} неизвестный тип ${prop.type}`)
    }
    if (prop.type === 'select' && !prop.options?.length) {
      throw new Error(`Блок ${type}: у поля ${where} нет options`)
    }
    if (prop.type === 'list') {
      if (!prop.item || !Object.keys(prop.item).length) throw new Error(`Блок ${type}: у списка ${where} нет item`)
      if (Object.values(prop.item).some((p) => p.type === 'list')) {
        throw new Error(`Блок ${type}: вложенные списки не поддерживаются (${where})`)
      }
      checkProps(type, prop.item, `${where}.`)
    }
  }
}

export function defineBlock(definition) {
  const {
    type,
    title,
    description = '',
    component,
    variants = ['default'],
    variantLabels = {},
    props = {},
    data = [],
    common = {},
    // Блоку нечего показать на сайте: секция и пункт меню скрываются
    isEmpty = () => false,
  } = definition
  if (!type || !title || !component) {
    throw new Error('Блок должен иметь type, title и component')
  }
  checkProps(type, props)
  return Object.freeze({ type, title, description, component, variants, variantLabels, props, data, common, isEmpty })
}
