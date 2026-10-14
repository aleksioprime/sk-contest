/**
 * Режим редактора: блоки получают контекст через provide/inject.
 * На опубликованном сайте контекста нет, и всё рендерится как обычный текст.
 */
import { inject } from 'vue'

export const EDITOR_KEY = Symbol('skb-editor')
export const BLOCK_KEY = Symbol('skb-block')

export function useEditor() {
  return inject(EDITOR_KEY, null)
}

export function useBlockId() {
  return inject(BLOCK_KEY, null)
}

/** Значение по пути «items.2.title». */
export function getPath(target, path) {
  return path.split('.').reduce((value, key) => (value == null ? undefined : value[key]), target)
}

/** Записать значение по пути, создавая промежуточные объекты. */
export function setPath(target, path, value) {
  const keys = path.split('.')
  let node = target
  for (const key of keys.slice(0, -1)) {
    if (node[key] == null) node[key] = {}
    node = node[key]
  }
  node[keys.at(-1)] = value
}
