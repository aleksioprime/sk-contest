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
