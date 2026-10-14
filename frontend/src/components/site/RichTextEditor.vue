<script setup>
/** Форматированный текст: жирный, курсив, подзаголовок, списки, цитата, ссылка. Без цветов и размеров. */
import StarterKit from '@tiptap/starter-kit'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import { onBeforeUnmount, watch } from 'vue'

defineProps({ label: { type: String, default: '' } })
const value = defineModel({ type: String, default: '' })

const editor = useEditor({
  content: value.value || '',
  extensions: [
    StarterKit.configure({
      heading: { levels: [3] },
      code: false,
      codeBlock: false,
      horizontalRule: false,
      link: { openOnClick: false, autolink: true, protocols: ['mailto', 'tel'] },
    }),
  ],
  editorProps: { attributes: { class: 'skb-richtext min-h-32 px-3 py-2 outline-none' } },
  onUpdate: ({ editor: e }) => {
    value.value = e.isEmpty ? '' : e.getHTML()
  },
})

// Внешние изменения (откат версии, другой блок) — заменяем содержимое, не сбивая курсор при наборе
watch(value, (html) => {
  if (editor.value && html !== editor.value.getHTML() && !(html === '' && editor.value.isEmpty)) {
    editor.value.commands.setContent(html || '', { emitUpdate: false })
  }
})

function link() {
  const previous = editor.value.getAttributes('link').href ?? ''
  const href = window.prompt('Ссылка (https://…, mailto:… или tel:…). Пусто — убрать ссылку', previous)
  if (href === null) return
  const chain = editor.value.chain().focus().extendMarkRange('link')
  if (!href.trim()) chain.unsetLink().run()
  else chain.setLink({ href: href.trim() }).run()
}

const buttons = [
  { title: 'Жирный', label: 'Ж', mark: 'bold', run: (c) => c.toggleBold(), class: 'font-bold' },
  { title: 'Курсив', label: 'К', mark: 'italic', run: (c) => c.toggleItalic(), class: 'italic' },
  { title: 'Подзаголовок', label: 'H', mark: 'heading', run: (c) => c.toggleHeading({ level: 3 }), class: 'font-semibold' },
  { title: 'Список', label: '•', mark: 'bulletList', run: (c) => c.toggleBulletList() },
  { title: 'Нумерованный список', label: '1.', mark: 'orderedList', run: (c) => c.toggleOrderedList() },
  { title: 'Цитата', label: '❝', mark: 'blockquote', run: (c) => c.toggleBlockquote() },
]

onBeforeUnmount(() => editor.value?.destroy())
</script>

<template>
  <div class="grid gap-1.5 text-sm">
    <span v-if="label" class="font-medium">{{ label }}</span>
    <div class="overflow-hidden rounded-control border border-line bg-surface focus-within:border-brand-500">
      <div v-if="editor" class="flex flex-wrap gap-0.5 border-b border-line bg-canvas p-1" role="toolbar" aria-label="Форматирование">
        <button
          v-for="b in buttons"
          :key="b.mark"
          type="button"
          :title="b.title"
          :aria-label="b.title"
          :aria-pressed="editor.isActive(b.mark)"
          class="h-7 min-w-7 rounded px-1.5"
          :class="[b.class, editor.isActive(b.mark) ? 'bg-brand-100 text-brand-700' : 'hover:bg-surface']"
          @click="b.run(editor.chain().focus()).run()"
        >
          {{ b.label }}
        </button>
        <button type="button" title="Ссылка" aria-label="Ссылка" class="h-7 rounded px-1.5" :class="editor.isActive('link') ? 'bg-brand-100 text-brand-700' : 'hover:bg-surface'" @click="link">
          🔗
        </button>
        <span class="mx-1 w-px bg-line" />
        <button type="button" title="Отменить" aria-label="Отменить" class="h-7 rounded px-1.5 hover:bg-surface" @click="editor.chain().focus().undo().run()">↶</button>
        <button type="button" title="Повторить" aria-label="Повторить" class="h-7 rounded px-1.5 hover:bg-surface" @click="editor.chain().focus().redo().run()">↷</button>
      </div>
      <EditorContent :editor="editor" />
    </div>
  </div>
</template>
