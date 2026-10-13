/**
 * Описание блока лендинга.
 *
 * Одна схема используется в трёх местах: редактор строит по ней форму настроек,
 * backend проверяет props перед сохранением (через toJsonSchema), а sites и превью рендерят компонент.
 */

export const PROP_TYPES = ['text', 'richtext', 'image', 'bool', 'select', 'cta', 'list']

export const COMMON_DEFAULTS = Object.freeze({
  anchor: '',
  inMenu: false,
  background: 'default', // default | muted | accent
  visibility: 'always', // always | registration | results
})

export function defineBlock(definition) {
  const { type, title, component, variants = ['default'], props = {}, data = [] } = definition
  if (!type || !title || !component) {
    throw new Error('Блок должен иметь type, title и component')
  }
  for (const [name, prop] of Object.entries(props)) {
    if (!PROP_TYPES.includes(prop.type)) {
      throw new Error(`Блок ${type}: у поля ${name} неизвестный тип ${prop.type}`)
    }
    if (prop.type === 'select' && !prop.options?.length) {
      throw new Error(`Блок ${type}: у поля ${name} нет options`)
    }
  }
  return Object.freeze({ type, title, component, variants, props, data })
}
