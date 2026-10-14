import { describe, expect, it } from 'vitest'
import { buildEventPage, formatRange, textToHtml } from '../lib/event-page.js'

const event = {
  slug: 'skolstart-2027',
  title: 'SkolStart 2027',
  short_description: 'Конференция проектов',
  description: 'Первый абзац.\n\nВторой <b>абзац</b>.',
  place: 'Гимназия Сколково',
  date_start: '2027-03-12',
  date_end: '2027-04-18',
  registration_open: true,
  directions: [{ title: 'Инженерия', description: '' }],
  stages: [{ title: 'Очная защита', kind: 'onsite', date_start: '2027-04-18', date_end: null }],
}

describe('formatRange', () => {
  it('сокращает диапазон в одном месяце и годе', () => {
    expect(formatRange('2027-03-12', '2027-03-14')).toBe('12–14 марта 2027')
    expect(formatRange('2027-03-12', '2027-04-18')).toBe('12 марта – 18 апреля 2027')
    expect(formatRange('2026-12-28', '2027-01-10')).toBe('28 декабря 2026 – 10 января 2027')
    expect(formatRange('2027-03-12', null)).toBe('12 марта 2027')
  })
})

describe('textToHtml', () => {
  it('экранирует HTML и делит на абзацы', () => {
    expect(textToHtml('a <script>\n\nb')).toBe('<p>a &lt;script&gt;</p><p>b</p>')
  })
})

describe('buildEventPage', () => {
  it('собирает страницу из данных мероприятия', () => {
    const site = buildEventPage(event, 'https://app.events.skolhub.ru/')
    expect(site.page.blocks.map((b) => b.id)).toEqual(['hero', 'about', 'directions', 'stages'])
    expect(site.page.blocks[0].props.ctaHref).toBe('https://app.events.skolhub.ru/events/skolstart-2027/apply')
    expect(site.page.blocks[1].props.body).toContain('&lt;b&gt;')
    expect(site.event.dates).toBe('12 марта – 18 апреля 2027')
  })

  it('прячет кнопку, когда приём закрыт', () => {
    const site = buildEventPage({ ...event, registration_open: false, description: '', directions: [], stages: [] }, '/')
    expect(site.page.blocks).toHaveLength(1)
    expect(site.page.blocks[0].props.ctaLabel).toBe('')
  })

  it('ставит обложку справа от заголовка', () => {
    const site = buildEventPage({ ...event, cover_url: '/api/v1/public/files/7' }, 'https://app.events.skolhub.ru')
    expect(site.page.blocks[0].variant).toBe('image-right')
    expect(site.page.blocks[0].props.image.url).toBe('https://app.events.skolhub.ru/api/v1/public/files/7')
  })

  it('ставит победителей сразу после обложки', () => {
    const results = [{ direction: 'Инженерия', winners: [{ rank: 1, award: 'winner', title: 'Теплица', participants: ['Анна <b>'] }] }]
    const site = buildEventPage(event, '/', results)
    expect(site.page.blocks[1].id).toBe('results')
    expect(site.page.blocks[1].props.body).toContain('1 место · Победитель')
    expect(site.page.blocks[1].props.body).toContain('Анна &lt;b&gt;')
  })
})
