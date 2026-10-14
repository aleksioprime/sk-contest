import { buildTemplate } from '@sk-events/blocks'
import { describe, expect, it } from 'vitest'
import { siteErrors } from '@/api/sites'

describe('ошибки сохранения сайта', () => {
  it('привязывает ошибки к блокам и полям', () => {
    const draft = buildTemplate('conference')
    const block = draft.pages[0].blocks[3]
    const error = {
      response: {
        data: {
          detail: {
            message: 'Сайт не сохранён',
            errors: [
              { where: 'pages.0.blocks.3.props.items.0.url', message: 'Неверная ссылка' },
              { where: 'theme.accent', message: 'Неверный цвет' },
            ],
          },
        },
      },
    }
    expect(siteErrors(error, draft)).toEqual([
      { where: 'pages.0.blocks.3.props.items.0.url', message: 'Неверная ссылка', blockId: block.id, field: 'items.0.url' },
      { where: 'theme.accent', message: 'Неверный цвет', blockId: null, field: '' },
    ])
  })

  it('без списка ошибок возвращает пустой список', () => {
    expect(siteErrors({ response: { data: { detail: 'Сайт ещё не создан' } } }, buildTemplate('selection'))).toEqual([])
  })
})
