import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

describe('UiButton', () => {
  it('показывает индикатор загрузки', () => {
    const wrapper = mount(UiButton, { props: { loading: true }, slots: { default: 'Сохранить' } })
    expect(wrapper.attributes('aria-busy')).toBe('true')
    expect(wrapper.text()).toBe('Сохранить')
  })
})

describe('UiInput', () => {
  it('связывает подпись и поле, показывает ошибку', () => {
    const wrapper = mount(UiInput, { props: { label: 'Название', error: 'Заполните поле' } })
    const input = wrapper.get('input')
    expect(wrapper.get('label').attributes('for')).toBe(input.attributes('id'))
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(wrapper.text()).toContain('Заполните поле')
  })

  it('обновляет v-model', async () => {
    const wrapper = mount(UiInput, { props: { modelValue: '', 'onUpdate:modelValue': (v) => wrapper.setProps({ modelValue: v }) } })
    await wrapper.get('input').setValue('SkolStart')
    expect(wrapper.props('modelValue')).toBe('SkolStart')
  })
})

describe('UiSelect', () => {
  const OPTIONS = '<option :value="null">Без этапа</option><option :value="1">Финал</option><option :value="2">Отбор</option>'
  const mountSelect = ({ modelValue = null, ...attrs } = {}, options = OPTIONS) =>
    mount(
      { components: { UiSelect }, props: ['attrs'], emits: ['pick'], data: () => ({ value: modelValue }), template: `<UiSelect v-model="value" v-bind="attrs" @update:model-value="$emit('pick', $event)">${options}</UiSelect>` },
      { props: { attrs }, attachTo: document.body },
    )
  const items = () => [...document.body.querySelectorAll('[role="option"]')]
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('показывает выбранный вариант и отдаёт значение с его типом', async () => {
    const wrapper = mountSelect({ modelValue: 1 })
    const trigger = wrapper.get('[role="combobox"]')
    expect(trigger.text()).toContain('Финал')
    await trigger.trigger('click')
    expect(items().map((li) => li.textContent.trim())).toEqual(['Без этапа', 'Финал', 'Отбор'])
    items()[2].click()
    await nextTick()
    expect(wrapper.emitted('pick')[0]).toEqual([2])
    expect(items()).toHaveLength(0)
    expect(trigger.text()).toContain('Отбор')
    wrapper.unmount()
  })

  it('выбирает с клавиатуры и закрывается по Escape', async () => {
    const wrapper = mountSelect()
    const trigger = wrapper.get('[role="combobox"]')
    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await nextTick()
    expect(trigger.attributes('aria-expanded')).toBe('true')
    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await trigger.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('pick')[0]).toEqual([1])
    await trigger.trigger('keydown', { key: 'ArrowDown' })
    await trigger.trigger('keydown', { key: 'Escape' })
    expect(trigger.attributes('aria-expanded')).toBe('false')
    wrapper.unmount()
  })

  it('выбор нескольких не закрывает список и хранит массив', async () => {
    const wrapper = mountSelect({ multiple: true, modelValue: [1] }, '<option :value="1">Финал</option><option :value="2">Отбор</option>')
    const trigger = wrapper.get('[role="combobox"]')
    await trigger.trigger('click')
    items()[1].click()
    await nextTick()
    expect(wrapper.emitted('pick')[0]).toEqual([[1, 2]])
    items()[0].click()
    await nextTick()
    expect(wrapper.emitted('pick')[1]).toEqual([[2]])
    expect(items()).toHaveLength(2)
    wrapper.unmount()
  })

  it('поиск включается на длинном списке и фильтрует варианты', async () => {
    const long = Array.from({ length: 12 }, (_, i) => `<option :value="${i}">Вариант ${i}</option>`).join('')
    const wrapper = mountSelect({}, long)
    await wrapper.get('[role="combobox"]').trigger('click')
    await nextTick()
    const search = document.body.querySelector('input[type="search"]')
    search.value = 'т 11'
    search.dispatchEvent(new Event('input'))
    await nextTick()
    expect(items().map((li) => li.textContent.trim())).toEqual(['Вариант 11'])
    wrapper.unmount()
  })

  it('короткий список без поиска, значение подсвечено как ошибка', async () => {
    const wrapper = mountSelect({ invalid: true })
    const trigger = wrapper.get('[role="combobox"]')
    expect(trigger.attributes('aria-invalid')).toBe('true')
    await trigger.trigger('click')
    await nextTick()
    expect(document.body.querySelector('input[type="search"]')).toBeNull()
    wrapper.unmount()
  })
})
