import { describe, expect, it } from 'vitest'
import { isValidSlug, pageUrl, resolveSite, siteApiPath } from '../lib/resolve-site.js'

const BASE = 'events.skolhub.ru'

describe('resolveSite', () => {
  it('поддомен', () => {
    expect(resolveSite('skolstart.events.skolhub.ru', '/', BASE)).toEqual({ kind: 'subdomain', slug: 'skolstart', page: '' })
    expect(resolveSite('skolstart.events.skolhub.ru', '/program', BASE)).toEqual({ kind: 'subdomain', slug: 'skolstart', page: 'program' })
  })

  it('путь на основном домене', () => {
    expect(resolveSite('events.skolhub.ru', '/skolstart/', BASE)).toEqual({ kind: 'path', slug: 'skolstart', page: '' })
    expect(resolveSite('localhost:3000', '/skolstart/program?x=1', BASE)).toEqual({ kind: 'path', slug: 'skolstart', page: 'program' })
  })

  it('корень основного домена', () => {
    expect(resolveSite('events.skolhub.ru', '/', BASE)).toEqual({ kind: 'root' })
  })

  it('свой домен', () => {
    expect(resolveSite('SkolStart.RU:443', '/', BASE)).toEqual({ kind: 'custom', domain: 'skolstart.ru', page: '' })
  })

  it('служебные и вложенные поддомены не считаются лендингами', () => {
    expect(resolveSite('app.events.skolhub.ru', '/', BASE)).toEqual({ kind: 'unknown' })
    expect(resolveSite('a.b.events.skolhub.ru', '/', BASE)).toEqual({ kind: 'unknown' })
  })
})

describe('isValidSlug', () => {
  it.each(['skolstart-2027', 'ui', 'a1'])('принимает %s', (slug) => expect(isValidSlug(slug)).toBe(true))
  it.each(['-a', 'a-', 'Skol', 'api', 'a_b', ''])('отклоняет %s', (slug) => expect(isValidSlug(slug)).toBe(false))
})

describe('адреса страниц и API', () => {
  it('строит ссылку на страницу с учётом вида адреса', () => {
    expect(pageUrl({ kind: 'path', slug: 'skolstart' }, 'https://events.skolhub.ru', 'program')).toBe('https://events.skolhub.ru/skolstart/program')
    expect(pageUrl({ kind: 'subdomain', slug: 'skolstart' }, 'https://skolstart.events.skolhub.ru', '')).toBe('https://skolstart.events.skolhub.ru')
  })

  it('выбирает API по виду адреса', () => {
    expect(siteApiPath({ kind: 'subdomain', slug: 'skolstart' })).toBe('/api/v1/public/sites/by-slug/skolstart')
    expect(siteApiPath({ kind: 'custom', domain: 'konkurs.ru' })).toBe('/api/v1/public/sites/by-domain/konkurs.ru')
  })
})
