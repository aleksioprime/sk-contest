import { COMMON_DEFAULTS } from './define.js'

const EMPTY_BY_TYPE = {
  text: '',
  richtext: '',
  image: null,
  bool: false,
  select: null,
  cta: null,
  list: [],
}

/** Начальные props нового блока. */
export function defaultProps(block) {
  const result = {}
  for (const [name, prop] of Object.entries(block.props)) {
    const fallback = prop.type === 'select' ? prop.options[0] : EMPTY_BY_TYPE[prop.type]
    result[name] = structuredClone(prop.default ?? fallback)
  }
  return result
}

/** Новый экземпляр блока для страницы. */
export function createBlockInstance(block, id) {
  return {
    id,
    type: block.type,
    variant: block.variants[0],
    props: defaultProps(block),
    common: { ...COMMON_DEFAULTS },
  }
}

/** Проверка props экземпляра. Возвращает список ошибок, пустой — значит всё верно. */
export function validateProps(block, props) {
  const errors = []
  for (const [name, prop] of Object.entries(block.props)) {
    const value = props?.[name]
    if (prop.required && (value === undefined || value === null || value === '')) {
      errors.push({ field: name, message: 'Заполните поле' })
      continue
    }
    if (value === undefined || value === null) continue
    if ((prop.type === 'text' || prop.type === 'richtext') && typeof value !== 'string') {
      errors.push({ field: name, message: 'Ожидается текст' })
    } else if (prop.type === 'text' && prop.max && value.length > prop.max) {
      errors.push({ field: name, message: `Не больше ${prop.max} символов` })
    } else if (prop.type === 'bool' && typeof value !== 'boolean') {
      errors.push({ field: name, message: 'Ожидается да или нет' })
    } else if (prop.type === 'select' && !prop.options.includes(value)) {
      errors.push({ field: name, message: 'Недопустимое значение' })
    } else if (prop.type === 'list' && !Array.isArray(value)) {
      errors.push({ field: name, message: 'Ожидается список' })
    }
  }
  return errors
}

/** JSON Schema props блока: backend проверяет по ней сохраняемый сайт. */
export function toJsonSchema(block) {
  const properties = {}
  const required = []
  for (const [name, prop] of Object.entries(block.props)) {
    properties[name] = jsonSchemaFor(prop)
    if (prop.required) required.push(name)
  }
  return {
    $id: `block:${block.type}`,
    type: 'object',
    properties,
    required,
    additionalProperties: false,
  }
}

function jsonSchemaFor(prop) {
  switch (prop.type) {
    case 'text':
      return { type: ['string', 'null'], ...(prop.max ? { maxLength: prop.max } : {}) }
    case 'richtext':
      return { type: ['string', 'null'] }
    case 'bool':
      return { type: 'boolean' }
    case 'select':
      return { enum: [...prop.options, null] }
    case 'list':
      return { type: 'array' }
    default:
      return { type: ['object', 'null'] }
  }
}
