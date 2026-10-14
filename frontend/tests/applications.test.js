import { describe, expect, it } from 'vitest'
import { fieldErrors, isVisible } from '@/api/applications'
import { errorMessage } from '@/api/http'

describe('isVisible', () => {
  const field = { key: 'school', visible_if: { field: 'external', equals: true } }

  it('показывает поле без условия', () => {
    expect(isVisible({ key: 'a' }, {})).toBe(true)
  })

  it('учитывает значение другого поля и списки', () => {
    expect(isVisible(field, { external: true })).toBe(true)
    expect(isVisible(field, { external: false })).toBe(false)
    expect(isVisible({ key: 'x', visible_if: { field: 'tags', equals: 'IT' } }, { tags: ['IT', 'Био'] })).toBe(true)
  })
})

describe('ошибки заявки', () => {
  const error = { response: { data: { detail: { message: 'Заявка заполнена не полностью', errors: { title: 'Укажите название' } } } } }

  it('достаёт общее сообщение и ошибки полей', () => {
    expect(errorMessage(error)).toBe('Заявка заполнена не полностью')
    expect(fieldErrors(error)).toEqual({ title: 'Укажите название' })
    expect(fieldErrors({ response: { data: { detail: 'текст' } } })).toEqual({})
  })
})
