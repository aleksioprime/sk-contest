import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { DECISION_ACTIONS, fieldErrors, isVisible } from '@/api/applications'
import { applyUrl } from '@/api/events'
import { errorMessage } from '@/api/http'
import ConsentsList from '@/components/applications/ConsentsList.vue'
import { resolveAccess, routes } from '@/router'

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

describe('открытая форма', () => {
  it('маршрут доступен без входа', () => {
    const route = routes.find((r) => r.name === 'apply')
    expect(route.path).toBe('/apply/:slug')
    expect(resolveAccess(route, { isAuthenticated: false })).toBe(true)
  })

  it('адрес формы строится по адресу мероприятия', () => {
    expect(applyUrl('skolstart')).toBe(`${window.location.origin}/apply/skolstart`)
  })

  it('для каждого решения сервера есть кнопка', () => {
    const decisions = ['confirmed', 'accepted', 'needs_changes', 'rejected', 'submitted', 'requested', 'draft']
    expect(decisions.filter((status) => !DECISION_ACTIONS[status])).toEqual([])
  })
})

describe('ConsentsList', () => {
  const consents = [{ key: 'pd', title: 'Данные', text: 'Текст', required: true }]

  it('отмечает согласие и показывает ошибку', async () => {
    const wrapper = mount(ConsentsList, {
      props: {
        consents,
        errors: { 'consent:pd': 'Нужно согласие' },
        modelValue: [],
        'onUpdate:modelValue': (value) => wrapper.setProps({ modelValue: value }),
      },
    })
    expect(wrapper.text()).toContain('Нужно согласие')
    await wrapper.get('input').setValue(true)
    expect(wrapper.props('modelValue')).toEqual(['pd'])
  })
})
