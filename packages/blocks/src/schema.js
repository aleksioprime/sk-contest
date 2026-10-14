import { COMMON_DEFAULTS } from './define.js'

const EMPTY_BY_TYPE = {
  text: '',
  richtext: '',
  url: '',
  image: null,
  file: null,
  bool: false,
  select: null,
  list: [],
}

export const URL_PATTERN = '^(https?://|mailto:|tel:|#|/)'
const URL_RE = new RegExp(URL_PATTERN)

function emptyValue(prop) {
  const fallback = prop.type === 'select' ? prop.options[0] : EMPTY_BY_TYPE[prop.type]
  return structuredClone(prop.default ?? fallback)
}

/** Начальные props нового блока или элемента списка. */
export function defaultProps(blockOrItem) {
  const fields = blockOrItem.props ?? blockOrItem
  const result = {}
  for (const [name, prop] of Object.entries(fields)) result[name] = emptyValue(prop)
  return result
}

/** Новый экземпляр блока для страницы. */
export function createBlockInstance(block, id) {
  return {
    id,
    type: block.type,
    variant: block.variants[0],
    hidden: false,
    props: defaultProps(block),
    common: { ...COMMON_DEFAULTS, ...block.common },
  }
}

function checkValue(prop, value, field, errors) {
  if (prop.required && (value === undefined || value === null || value === '')) {
    errors.push({ field, message: 'Заполните поле' })
    return
  }
  if (value === undefined || value === null) return
  const isText = prop.type === 'text' || prop.type === 'richtext' || prop.type === 'url'
  if (isText && typeof value !== 'string') {
    errors.push({ field, message: 'Ожидается текст' })
  } else if (prop.type === 'text' && prop.max && value.length > prop.max) {
    errors.push({ field, message: `Не больше ${prop.max} символов` })
  } else if (prop.type === 'url' && value && !URL_RE.test(value)) {
    errors.push({ field, message: 'Ссылка должна начинаться с https://, mailto:, tel: или #' })
  } else if (prop.type === 'bool' && typeof value !== 'boolean') {
    errors.push({ field, message: 'Ожидается да или нет' })
  } else if (prop.type === 'select' && !prop.options.includes(value)) {
    errors.push({ field, message: 'Недопустимое значение' })
  } else if ((prop.type === 'image' || prop.type === 'file') && (typeof value !== 'object' || !value.url)) {
    errors.push({ field, message: 'Загрузите файл' })
  } else if (prop.type === 'list') {
    if (!Array.isArray(value)) {
      errors.push({ field, message: 'Ожидается список' })
    } else {
      if (prop.max && value.length > prop.max) errors.push({ field, message: `Не больше ${prop.max} элементов` })
      value.forEach((item, index) => {
        for (const [name, itemProp] of Object.entries(prop.item)) {
          checkValue(itemProp, item?.[name], `${field}.${index}.${name}`, errors)
        }
      })
    }
  }
}

/** Проверка props экземпляра. Возвращает список ошибок, пустой — значит всё верно. */
export function validateProps(block, props) {
  const errors = []
  for (const [name, prop] of Object.entries(block.props)) checkValue(prop, props?.[name], name, errors)
  return errors
}

/** JSON Schema props блока: backend проверяет по ней сохраняемый сайт. */
export function toJsonSchema(block) {
  return {
    $id: `block:${block.type}`,
    ...objectSchema(block.props),
    'x-variants': block.variants,
  }
}

function objectSchema(fields) {
  const properties = {}
  const required = []
  for (const [name, prop] of Object.entries(fields)) {
    properties[name] = jsonSchemaFor(prop)
    if (prop.required) required.push(name)
  }
  return { type: 'object', properties, required, additionalProperties: false }
}

const ASSET = {
  type: ['object', 'null'],
  properties: {
    file_id: { type: ['integer', 'null'] },
    url: { type: 'string', maxLength: 500 },
    alt: { type: 'string', maxLength: 300 },
    name: { type: 'string', maxLength: 255 },
  },
  required: ['url'],
  additionalProperties: false,
}

function jsonSchemaFor(prop) {
  switch (prop.type) {
    case 'text':
      return { type: ['string', 'null'], maxLength: prop.max ?? 5000 }
    case 'richtext':
      // HTML очищается на сервере по списку разрешённых тегов
      return { type: ['string', 'null'], maxLength: 50000, 'x-richtext': true }
    case 'url':
      return { type: ['string', 'null'], maxLength: 1000, anyOf: [{ const: '' }, { pattern: URL_PATTERN }, { type: 'null' }] }
    case 'bool':
      return { type: 'boolean' }
    case 'select':
      return { enum: [...prop.options, null] }
    case 'list':
      return { type: 'array', maxItems: prop.max ?? 100, items: objectSchema(prop.item) }
    default:
      return ASSET
  }
}
