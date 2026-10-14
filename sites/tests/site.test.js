import { describe, expect, it } from 'vitest'
import { buildSite } from '../lib/site.js'

const event = {
  slug: 'skolstart-2027',
  type: 'project_contest',
  title: 'SkolStart 2027',
  short_description: 'Конкурс проектов',
  description: 'О конкурсе',
  registration_open: true,
  cover_url: '/api/v1/public/files/7',
  directions: [],
  stages: [],
}
const APP = 'https://app.events.skolhub.ru'

describe('buildSite', () => {
  it('без опубликованной версии собирает сайт по шаблону типа мероприятия', () => {
    const site = buildSite({ event, content: null, results: [] }, { appUrl: APP })
    const types = site.page.blocks.map((b) => b.type)
    expect(types).toContain('hero')
    expect(types).toContain('registration')
    expect(site.phase).toBe('registration')
    expect(site.seo.title).toBe('SkolStart 2027')
    expect(site.seo.image).toBe(`${APP}/api/v1/public/files/7`)
  })

  it('берёт опубликованную версию, страницу по адресу и SEO из настроек', () => {
    const content = {
      theme: { accent: '#0f6e56' },
      pages: [
        { path: '', title: 'Главная', blocks: [] },
        { path: 'program', title: 'Программа', blocks: [{ id: 'p', type: 'program', variant: 'list', props: {}, common: {} }] },
      ],
      seo: { title: 'SkolStart', description: 'Лучший конкурс', image: null, metrika: '123' },
    }
    const payload = { event, content, results: [{ direction: '', winners: [] }], domain: 'konkurs.ru' }
    const site = buildSite(payload, { appUrl: APP, page: 'program' })
    expect(site.page.title).toBe('Программа')
    expect(site.seo.title).toBe('Программа · SkolStart')
    expect(site.seo.metrika).toBe('123')
    expect(site.phase).toBe('results')
    expect(site.domain).toBe('konkurs.ru')
    expect(buildSite(payload, { appUrl: APP, page: 'missing' })).toBeNull()
  })
})
