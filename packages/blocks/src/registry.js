import hero from './blocks/hero/index.js'
import text from './blocks/text/index.js'

export const blocks = Object.freeze({
  [hero.type]: hero,
  [text.type]: text,
})

export function getBlock(type) {
  const block = blocks[type]
  if (!block) throw new Error(`Неизвестный блок: ${type}`)
  return block
}
