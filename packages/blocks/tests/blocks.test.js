import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { SitePage, blocks, createBlockInstance, defineBlock, getBlock, toJsonSchema, validateProps } from '../src/index.js'

describe('схема блока', () => {
  it('создаёт экземпляр с props по умолчанию', () => {
    const hero = createBlockInstance(getBlock('hero'), 'b1')
    expect(hero.variant).toBe('image-bg')
    expect(hero.props.ctaLabel).toBe('Подать заявку')
    expect(hero.props.countdown).toBe(false)
    expect(hero.common.visibility).toBe('always')
  })

  it('находит ошибки в props', () => {
    const errors = validateProps(getBlock('hero'), { title: 'x'.repeat(121), countdown: 'да' })
    expect(errors.map((e) => e.field)).toEqual(['title', 'countdown'])
  })

  it('отдаёт JSON Schema без лишних полей', () => {
    const schema = toJsonSchema(getBlock('hero'))
    expect(schema.additionalProperties).toBe(false)
    expect(schema.properties.title.maxLength).toBe(120)
  })

  it('не принимает неизвестный тип поля', () => {
    expect(() => defineBlock({ type: 'x', title: 'X', component: {}, props: { a: { type: 'html' } } })).toThrow()
  })

  it('у каждого блока есть компонент и варианты', () => {
    for (const block of Object.values(blocks)) {
      expect(block.component).toBeTruthy()
      expect(block.variants.length).toBeGreaterThan(0)
    }
  })
})

describe('SitePage', () => {
  const page = {
    blocks: [
      { ...createBlockInstance(getBlock('hero'), 'b1'), props: { ...createBlockInstance(getBlock('hero'), 'b1').props, title: 'SkolStart 2027' } },
      { ...createBlockInstance(getBlock('text'), 'b2'), props: { title: 'О конференции', body: '<p>Текст</p>' } },
      { ...createBlockInstance(getBlock('text'), 'b3'), props: { title: 'Победители', body: '' }, common: { visibility: 'results' } },
    ],
  }

  it('рендерит блоки и подставляет тему', () => {
    const wrapper = mount(SitePage, { props: { page, theme: { accent: '#0f6e56' }, event: { dates: '12 марта – 18 апреля' } } })
    expect(wrapper.text()).toContain('SkolStart 2027')
    expect(wrapper.text()).toContain('12 марта – 18 апреля')
    expect(wrapper.attributes('style')).toContain('--skb-accent: #0f6e56')
  })

  it('прячет блоки по правилу показа', () => {
    expect(mount(SitePage, { props: { page, phase: 'registration' } }).text()).not.toContain('Победители')
    expect(mount(SitePage, { props: { page, phase: 'results' } }).text()).toContain('Победители')
  })
})
