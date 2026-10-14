import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import EvaluationForm from '@/components/evaluation/EvaluationForm.vue'

const scorecard = {
  max_score: '4.00',
  categories: [{ id: 1, title: 'Содержание' }],
  criteria: [
    {
      id: 10, title: 'Актуальность', description: '', type: 'scale', weight: '1.00', category_id: 1, options: [],
      scale: { levels: [{ id: 100, title: 'Нет', points: '0' }, { id: 101, title: 'Да', points: '2' }] },
    },
    {
      id: 11, title: 'Результаты', description: '', type: 'checklist', weight: '1.00', category_id: null, scale: null,
      options: [{ id: 200, title: 'Прототип', points: '1', is_exclusive: false }, { id: 201, title: 'Испытания', points: '1', is_exclusive: false }],
    },
  ],
}

function bundle(items = []) {
  return { evaluation_id: 1, editable: true, scorecard, items, score: null, is_scored: false, comment: '' }
}

function mountForm(items = []) {
  const client = { setCriterion: vi.fn().mockResolvedValue(bundle(items)), setComment: vi.fn() }
  const wrapper = mount(EvaluationForm, { props: { bundle: bundle(items), client } })
  return { wrapper, client }
}

describe('EvaluationForm', () => {
  it('группирует критерии по категориям', () => {
    const { wrapper } = mountForm()
    expect(wrapper.findAll('h2').map((h) => h.text())).toEqual(['Содержание', 'Другое'])
    expect(wrapper.text()).toContain('Оценено критериев: 0 из 2')
  })

  it('выбирает уровень и снимает его повторным нажатием', async () => {
    const { wrapper, client } = mountForm()
    await wrapper.findAll('[role="radio"]')[1].trigger('click')
    expect(client.setCriterion).toHaveBeenCalledWith(10, { level_id: 101 })

    const picked = mountForm([{ criterion_id: 10, level_id: 101, option_ids: [], score: '2', comment: '' }])
    await picked.wrapper.findAll('[role="radio"]')[1].trigger('click')
    expect(picked.client.setCriterion).toHaveBeenCalledWith(10, { clear: true })
  })

  it('отправляет выбранные пункты чек-листа', async () => {
    const { wrapper, client } = mountForm([{ criterion_id: 11, level_id: null, option_ids: [200], score: '1', comment: '' }])
    await wrapper.findAll('input[type="checkbox"]')[1].trigger('change')
    expect(client.setCriterion).toHaveBeenCalledWith(11, { option_ids: [200, 201] })
    await flushPromises()
    expect(wrapper.emitted('update:bundle')).toHaveLength(1)
  })
})
