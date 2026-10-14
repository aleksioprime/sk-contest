// @vitest-environment node
/**
 * Схемы блоков для backend: он проверяет по ним сохраняемый сайт.
 * Обновить файл после изменения блоков: npm run schema --workspace packages/blocks
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { COMMON_DEFAULTS, blocks, toJsonSchema } from '../src/index.js'

const TARGET = fileURLToPath(new URL('../../../backend/app/modules/sites/block_schemas.json', import.meta.url))

function exported() {
  return {
    common: Object.keys(COMMON_DEFAULTS),
    blocks: Object.fromEntries(Object.values(blocks).map((block) => [block.type, toJsonSchema(block)])),
  }
}

describe('схемы блоков для backend', () => {
  it('файл совпадает с описанием блоков', () => {
    const text = `${JSON.stringify(exported(), null, 2)}\n`
    if (process.env.UPDATE_SCHEMA) writeFileSync(TARGET, text)
    expect(existsSync(TARGET), 'Запустите npm run schema --workspace packages/blocks').toBe(true)
    expect(readFileSync(TARGET, 'utf8')).toBe(text)
  })
})
