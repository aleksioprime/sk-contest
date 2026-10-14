import dates from './blocks/dates/index.js'
import directions from './blocks/directions/index.js'
import documents from './blocks/documents/index.js'
import faq from './blocks/faq/index.js'
import footer from './blocks/footer/index.js'
import gallery from './blocks/gallery/index.js'
import header from './blocks/header/index.js'
import hero from './blocks/hero/index.js'
import partners from './blocks/partners/index.js'
import people from './blocks/people/index.js'
import program from './blocks/program/index.js'
import registration from './blocks/registration/index.js'
import results from './blocks/results/index.js'
import stats from './blocks/stats/index.js'
import text from './blocks/text/index.js'

/** Порядок — как в палитре редактора. */
const ORDER = [header, hero, text, dates, directions, stats, program, people, registration, results, documents, partners, faq, gallery, footer]

export const blocks = Object.freeze(Object.fromEntries(ORDER.map((block) => [block.type, block])))

export function getBlock(type) {
  const block = blocks[type]
  if (!block) throw new Error(`Неизвестный блок: ${type}`)
  return block
}
