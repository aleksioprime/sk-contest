import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

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
