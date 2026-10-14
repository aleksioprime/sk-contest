import { describe, expect, it } from 'vitest'
import { isValidSlug, resolveSite } from '../lib/resolve-site.js'

const BASE = 'events.skolhub.ru'

describe('resolveSite', () => {
  it('поддомен', () => {
    expect(resolveSite('skolstart.events.skolhub.ru', '/', BASE)).toEqual({ kind: 'subdomain', slug: 'skolstart' })
  })

  it('путь на основном домене', () => {
    expect(resolveSite('events.skolhub.ru', '/skolstart/', BASE)).toEqual({ kind: 'path', slug: 'skolstart' })
    expect(resolveSite('localhost:3000', '/skolstart', BASE)).toEqual({ kind: 'path', slug: 'skolstart' })
  })

  it('корень основного домена', () => {
    expect(resolveSite('events.skolhub.ru', '/', BASE)).toEqual({ kind: 'root' })
  })

  it('свой домен', () => {
    expect(resolveSite('SkolStart.RU:443', '/', BASE)).toEqual({ kind: 'custom', domain: 'skolstart.ru' })
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
