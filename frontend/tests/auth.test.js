import { describe, expect, it } from 'vitest'
import { errorMessage } from '@/api/http'
import { resolveAccess } from '@/router'

const route = (meta = {}, fullPath = '/admin/people') => ({ meta, fullPath })

describe('resolveAccess', () => {
  it('пускает на публичные страницы без входа', () => {
    expect(resolveAccess(route({ public: true }), { isAuthenticated: false })).toBe(true)
  })

  it('отправляет на вход и запоминает адрес', () => {
    expect(resolveAccess(route(), { isAuthenticated: false })).toEqual({
      name: 'login',
      query: { next: '/admin/people' },
    })
  })

  it('не пускает в админку без прав', () => {
    expect(resolveAccess(route({ admin: true }), { isAuthenticated: true, isAdmin: false })).toEqual({ name: 'home' })
    expect(resolveAccess(route({ admin: true }), { isAuthenticated: true, isAdmin: true })).toBe(true)
  })
})

describe('errorMessage', () => {
  it('берёт текст ошибки API', () => {
    expect(errorMessage({ response: { data: { detail: 'Ссылка устарела' } } })).toBe('Ссылка устарела')
  })

  it('объясняет ошибку сети и валидации', () => {
    expect(errorMessage({})).toBe('Сервер недоступен. Проверьте подключение.')
    expect(errorMessage({ response: { data: { detail: [{}] } } })).toBe('Проверьте правильность заполнения полей')
  })
})

describe('slugify', async () => {
  const { slugify } = await import('@/api/events')
  it('транслитерирует название в адрес', () => {
    expect(slugify('SkolStart 2027')).toBe('skolstart-2027')
    expect(slugify('Юный исследователь — весна!')).toBe('yunyy-issledovatel-vesna')
    expect(slugify('  --Тест--  ')).toBe('test')
  })
})

describe('formatRange', async () => {
  const { formatRange } = await import('@/utils/dates')
  it('сокращает диапазон дат', () => {
    expect(formatRange('2027-04-10', '2027-04-11')).toBe('10–11 апреля 2027')
    expect(formatRange('2027-03-12', '2027-04-18')).toBe('12 марта – 18 апреля 2027')
    expect(formatRange(null, null)).toBe('')
  })
})
