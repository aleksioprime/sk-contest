import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { h, reactive } from 'vue'
import {
  EDITOR_KEY,
  SitePage,
  TEMPLATES,
  blocks,
  buildSiteData,
  buildTemplate,
  createBlockInstance,
  defineBlock,
  getBlock,
  safeHref,
  setPath,
  toJsonSchema,
  validateProps,
} from '../src/index.js'

const instance = (type, id, props = {}, extra = {}) => {
  const block = createBlockInstance(getBlock(type), id)
  return { ...block, ...extra, props: { ...block.props, ...props }, common: { ...block.common, ...extra.common } }
}

const payload = {
  event: {
    slug: 'skolstart-2027',
    title: 'SkolStart 2027',
    date_start: '2027-03-12',
    date_end: '2027-04-18',
    place: 'Гимназия Сколково',
    registration_open: true,
    registration_closes_at: '2027-03-01T20:59:00Z',
    directions: [{ title: 'Инженерия', description: 'Роботы и датчики' }],
    stages: [{ title: 'Заочный отбор', kind: 'remote', date_start: '2027-03-12', date_end: '2027-03-20' }],
  },
  results: [{ direction: 'Инженерия', winners: [{ rank: 1, award: 'winner', title: 'Умная теплица', participants: ['Иванова Анна'] }] }],
  program: [{ starts_at: '2027-04-18T07:00:00Z', ends_at: '2027-04-18T09:00:00Z', room: '301', title: 'Секция 1', stage: 'Финал', works: [{ number: 1, title: 'Умная теплица' }] }],
}
const data = buildSiteData(payload, { appUrl: 'https://app.events.skolhub.ru' })

describe('схема блока', () => {
  it('создаёт экземпляр с props и общими настройками по умолчанию', () => {
    const hero = createBlockInstance(getBlock('hero'), 'b1')
    expect(hero.variant).toBe('image-bg')
    expect(hero.props.ctaLabel).toBe('Подать заявку')
    expect(hero.props.countdown).toBe(false)
    expect(hero.common.visibility).toBe('always')
    expect(createBlockInstance(getBlock('registration'), 'b2').common.anchor).toBe('registration')
  })

  it('находит ошибки в props, в том числе в элементах списка', () => {
    const errors = validateProps(getBlock('hero'), { title: 'x'.repeat(121), countdown: 'да', ctaHref: 'javascript:alert(1)' })
    expect(errors.map((e) => e.field)).toEqual(['title', 'ctaHref', 'countdown'])
    const listErrors = validateProps(getBlock('partners'), { items: [{ name: 'Ок', url: 'ftp://x' }] })
    expect(listErrors.map((e) => e.field)).toEqual(['items.0.url'])
  })

  it('отдаёт JSON Schema без лишних полей и со схемой элементов списка', () => {
    const schema = toJsonSchema(getBlock('hero'))
    expect(schema.additionalProperties).toBe(false)
    expect(schema.properties.title.maxLength).toBe(120)
    const faq = toJsonSchema(getBlock('faq'))
    expect(faq.properties.items.items.properties.answer.maxLength).toBe(3000)
    expect(toJsonSchema(getBlock('text')).properties.body['x-richtext']).toBe(true)
  })

  it('не принимает неизвестный тип поля и вложенные списки', () => {
    expect(() => defineBlock({ type: 'x', title: 'X', component: {}, props: { a: { type: 'html' } } })).toThrow()
    const nested = { type: 'list', item: { inner: { type: 'list', item: { a: { type: 'text' } } } } }
    expect(() => defineBlock({ type: 'x', title: 'X', component: {}, props: { a: nested } })).toThrow()
  })

  it('в первой версии 15 блоков, у каждого компонент и варианты с подписями', () => {
    expect(Object.keys(blocks)).toHaveLength(15)
    for (const block of Object.values(blocks)) {
      expect(block.component).toBeTruthy()
      expect(block.variants.length).toBeGreaterThan(0)
      if (block.variants.length > 1) expect(Object.keys(block.variantLabels)).toEqual(block.variants)
    }
  })

  it('пропускает только безопасные ссылки', () => {
    expect(safeHref('https://skolkovo.ru')).toBe('https://skolkovo.ru')
    expect(safeHref('#registration')).toBe('#registration')
    expect(safeHref('javascript:alert(1)')).toBe('')
    expect(safeHref('//evil.example')).toBe('')
  })
})

describe('шаблоны', () => {
  it('для каждого типа мероприятия собирают страницу из известных блоков', () => {
    for (const type of Object.keys(TEMPLATES)) {
      const site = buildTemplate(type, { description: 'Первый абзац\n\nВторой' })
      const types = site.pages[0].blocks.map((b) => b.type)
      expect(types[0]).toBe('header')
      expect(types.at(-1)).toBe('footer')
      expect(new Set(site.pages[0].blocks.map((b) => b.id)).size).toBe(types.length)
      expect(site.theme.accent).toMatch(/^#/)
    }
    const text = buildTemplate('conference', { description: 'A <b>\n\nB' }).pages[0].blocks.find((b) => b.type === 'text')
    expect(text.props.body).toBe('<p>A &lt;b&gt;</p><p>B</p>')
  })
})

describe('SitePage', () => {
  const page = {
    blocks: [
      instance('header', 'h'),
      instance('hero', 'b1', { title: 'SkolStart 2027' }),
      instance('dates', 'b2'),
      instance('results', 'b3'),
      instance('program', 'b4'),
      instance('text', 'b5', { title: 'Только после итогов', body: '<p>Текст</p>' }, { common: { visibility: 'results' } }),
    ],
  }

  it('рендерит блоки с данными мероприятия и подставляет тему', () => {
    const wrapper = mount(SitePage, { props: { page, theme: { accent: '#0f6e56', mode: 'dark' }, data, phase: 'registration' } })
    const text = wrapper.text()
    expect(text).toContain('SkolStart 2027')
    expect(text).toContain('12 марта – 18 апреля 2027')
    expect(text).toContain('Заочный отбор')
    expect(text).toContain('Приём заявок')
    expect(text).toContain('Умная теплица')
    expect(text).toContain('10:00–12:00') // время по Москве
    expect(wrapper.attributes('style')).toContain('--skb-accent: #0f6e56')
    expect(wrapper.attributes('style')).toContain('--skb-bg: #14121c')
    // меню из блоков с якорем и названием пункта
    expect(wrapper.findAll('.skb-header__nav a').map((a) => a.attributes('href'))).toEqual(['#dates', '#results', '#program'])
  })

  it('прячет блоки по правилу показа и блок итогов без итогов', () => {
    expect(mount(SitePage, { props: { page, data, phase: 'registration' } }).text()).not.toContain('Только после итогов')
    expect(mount(SitePage, { props: { page, data, phase: 'results' } }).text()).toContain('Только после итогов')
    const empty = buildSiteData({ ...payload, results: [] })
    expect(mount(SitePage, { props: { page, data: empty } }).find('.skb-results').exists()).toBe(false)
  })

  it('в редакторе текст правится на превью, клик выбирает блок', async () => {
    const editor = reactive({
      selectedId: null,
      changes: [],
      select(id) {
        this.selectedId = id
      },
      update(id, path, value) {
        this.changes.push([id, path, value])
      },
    })
    const wrapper = mount({ render: () => h(SitePage, { page, data: { ...data, editing: true } }) }, {
      global: { provide: { [EDITOR_KEY]: editor } },
    })
    const title = wrapper.find('.skb-hero__title')
    expect(title.attributes('contenteditable')).toBe('plaintext-only')
    title.element.innerText = 'Новый заголовок'
    await title.trigger('blur')
    expect(editor.changes).toEqual([['b1', 'title', 'Новый заголовок']])
    await wrapper.find('[data-block-id="b2"]').trigger('click')
    expect(editor.selectedId).toBe('b2')
  })
})

describe('setPath', () => {
  it('пишет значение во вложенный список', () => {
    const props = { items: [{ title: 'a' }] }
    setPath(props, 'items.0.title', 'b')
    expect(props.items[0].title).toBe('b')
  })
})
