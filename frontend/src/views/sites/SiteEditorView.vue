<script setup>
import '@sk-events/blocks/styles.css'
import {
  EDITOR_KEY,
  SitePage,
  TEMPLATES,
  buildSiteData,
  buildTemplate,
  createBlockInstance,
  getBlock,
  newBlockId,
  setPath,
  sitePhase,
  themeFontsHref,
} from '@sk-events/blocks'
import { computed, onBeforeUnmount, onMounted, provide, reactive, ref, watch } from 'vue'
import { RouterLink, onBeforeRouteLeave } from 'vue-router'
import { fetchEvent } from '@/api/events'
import { errorMessage } from '@/api/http'
import { fetchSite, fetchSiteData, publishSite, saveSite, siteErrors, unpublishSite } from '@/api/sites'
import BlockPalette from '@/components/site/BlockPalette.vue'
import BlockSettings from '@/components/site/BlockSettings.vue'
import DomainsPanel from '@/components/site/DomainsPanel.vue'
import PagesPanel from '@/components/site/PagesPanel.vue'
import SeoPanel from '@/components/site/SeoPanel.vue'
import ThemePanel from '@/components/site/ThemePanel.vue'
import VersionsPanel from '@/components/site/VersionsPanel.vue'
import SkeletonPage from '@/components/skeleton/SkeletonPage.vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({ id: { type: String, required: true } })

const event = ref(null)
const site = ref(null)
const payload = ref(null)
const draft = ref(null)
const loadError = ref('')
const pageIndex = ref(0)
const selectedId = ref(null)
const panel = ref('theme')
const device = ref('desktop')
const phase = ref('registration')
const saveState = ref('saved') // saved | dirty | saving | error
const errors = ref([])
const notice = ref('')
const showPalette = ref(false)
const removing = ref(null)
const publishing = ref(false)
const confirmUnpublish = ref(false)
const dragging = ref(null)
const versionsPanel = ref(null)
const templateType = ref('')

const page = computed(() => draft.value?.pages[pageIndex.value])
const selected = computed(() => page.value?.blocks.find((b) => b.id === selectedId.value) ?? null)
const previewData = computed(() => buildSiteData(payload.value ?? {}, { appUrl: window.location.origin, editing: true }))
const blockErrors = computed(() => errors.value.filter((e) => e.blockId === selectedId.value))
const erroredBlocks = computed(() => new Set(errors.value.map((e) => e.blockId).filter(Boolean)))
const canPublish = computed(() => site.value?.exists && saveState.value === 'saved' && site.value.has_unpublished_changes)

// --- Контекст редактора для блоков: выбор и правка текста прямо на превью ---
provide(
  EDITOR_KEY,
  reactive({
    selectedId,
    select(id) {
      selectedId.value = id
    },
    update(blockId, path, value) {
      const block = page.value.blocks.find((b) => b.id === blockId)
      if (block) setPath(block.props, path, value)
    },
  }),
)

async function load() {
  try {
    const [ev, current, data] = await Promise.all([fetchEvent(props.id), fetchSite(props.id), fetchSiteData(props.id)])
    event.value = ev
    payload.value = data
    phase.value = sitePhase(data)
    templateType.value = TEMPLATES[ev.type] ? ev.type : 'project_contest'
    applySite(current)
  } catch (e) {
    loadError.value = errorMessage(e)
  }
}

function applySite(current) {
  site.value = current
  if (current.exists) {
    skipNextChange = true
    draft.value = structuredClone(current.draft)
    pageIndex.value = Math.min(pageIndex.value, draft.value.pages.length - 1)
  }
}

async function create() {
  skipNextChange = true
  draft.value = buildTemplate(templateType.value, event.value)
  await save()
}

// --- Автосохранение черновика ---
let timer = null
let skipNextChange = false

watch(
  draft,
  () => {
    if (skipNextChange) {
      skipNextChange = false
      return
    }
    if (!draft.value) return
    saveState.value = 'dirty'
    clearTimeout(timer)
    timer = setTimeout(save, 1000)
  },
  { deep: true },
)

async function save() {
  clearTimeout(timer)
  saveState.value = 'saving'
  const snapshot = JSON.stringify(draft.value)
  try {
    const result = await saveSite(props.id, JSON.parse(snapshot))
    site.value = result
    errors.value = []
    // Пока сохраняли, могли продолжить править — тогда сохраним ещё раз
    if (JSON.stringify(draft.value) === snapshot) saveState.value = 'saved'
    else timer = setTimeout(save, 500)
    return true
  } catch (e) {
    errors.value = siteErrors(e, draft.value)
    if (!errors.value.length) errors.value = [{ where: '', message: errorMessage(e), blockId: null, field: '' }]
    saveState.value = 'error'
    return false
  }
}

async function publish() {
  publishing.value = true
  notice.value = ''
  try {
    if (saveState.value !== 'saved' && !(await save())) return
    site.value = await publishSite(props.id)
    notice.value = 'Сайт опубликован'
    versionsPanel.value?.load()
  } catch (e) {
    errors.value = [{ where: '', message: errorMessage(e), blockId: null, field: '' }]
  } finally {
    publishing.value = false
  }
}

async function unpublish() {
  confirmUnpublish.value = false
  site.value = await unpublishSite(props.id)
  notice.value = 'Сайт снят с публикации: посетители видят страницу по шаблону'
  versionsPanel.value?.load()
}

// --- Блоки страницы ---
function addBlock(type) {
  showPalette.value = false
  const block = createBlockInstance(getBlock(type), newBlockId())
  // Якорь уже занят — блок без якоря, чтобы ссылки меню не путались
  const anchors = new Set(page.value.blocks.map((b) => b.common.anchor).filter(Boolean))
  if (anchors.has(block.common.anchor)) block.common = { ...block.common, anchor: '', menuTitle: '' }
  const blocks = page.value.blocks
  const at = selected.value ? blocks.indexOf(selected.value) + 1 : blocks.at(-1)?.type === 'footer' ? blocks.length - 1 : blocks.length
  blocks.splice(at, 0, block)
  selectedId.value = block.id
}

function duplicate(block) {
  const copy = { ...structuredClone(block), id: newBlockId(), common: { ...block.common, anchor: '', menuTitle: '' } }
  page.value.blocks.splice(page.value.blocks.indexOf(block) + 1, 0, copy)
  selectedId.value = copy.id
}

function remove(block) {
  page.value.blocks.splice(page.value.blocks.indexOf(block), 1)
  removing.value = null
  if (selectedId.value === block.id) selectedId.value = null
}

function drop(index) {
  if (dragging.value === null || dragging.value === index) return
  const blocks = page.value.blocks
  const [moved] = blocks.splice(dragging.value, 1)
  blocks.splice(index, 0, moved)
  dragging.value = null
}

function scrollToBlock(id) {
  selectedId.value = id
  document.querySelector(`[data-block-id="${id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// --- Страницы ---
function addPage(title) {
  const used = new Set(draft.value.pages.map((p) => p.path))
  let path = `page-${draft.value.pages.length}`
  while (used.has(path)) path += '-1'
  draft.value.pages.push({ path, title, blocks: [createBlockInstance(getBlock('header'), newBlockId()), createBlockInstance(getBlock('text'), newBlockId())] })
  pageIndex.value = draft.value.pages.length - 1
  selectedId.value = null
}

function updatePage(index, changes) {
  Object.assign(draft.value.pages[index], changes)
}

function removePage(index) {
  draft.value.pages.splice(index, 1)
  pageIndex.value = 0
  selectedId.value = null
}

// --- Шрифты темы в превью ---
watch(
  () => draft.value?.theme?.fontPair,
  (pair) => {
    if (!pair) return
    let link = document.getElementById('skb-fonts')
    if (!link) {
      link = Object.assign(document.createElement('link'), { id: 'skb-fonts', rel: 'stylesheet' })
      document.head.append(link)
    }
    link.href = themeFontsHref(draft.value.theme)
  },
)

function beforeUnload(e) {
  if (saveState.value !== 'saved') e.preventDefault()
}
onMounted(() => {
  window.addEventListener('beforeunload', beforeUnload)
  load()
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnload)
  clearTimeout(timer)
})
onBeforeRouteLeave(async () => {
  if (saveState.value === 'dirty') await save()
  return saveState.value !== 'error' || window.confirm('Последние изменения не сохранились. Уйти со страницы?')
})

const SAVE_LABELS = { saved: 'Все изменения сохранены', dirty: 'Есть изменения…', saving: 'Сохранение…', error: 'Не сохранено' }
const PHASES = { registration: 'Во время приёма заявок', results: 'После публикации итогов', always: 'Вне приёма заявок' }
const PANELS = { theme: 'Тема', seo: 'SEO', pages: 'Страницы', domains: 'Адрес', versions: 'Версии' }
</script>

<template>
  <div class="grid h-dvh grid-rows-[auto_minmax(0,1fr)] bg-canvas">
    <header class="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-surface px-4 py-2">
      <RouterLink :to="{ name: 'event', params: { id } }" class="text-sm text-ink-muted hover:text-ink">← {{ event?.title ?? 'Мероприятие' }}</RouterLink>
      <p class="font-semibold">Сайт мероприятия</p>
      <template v-if="draft">
        <select v-if="draft.pages.length > 1" v-model="pageIndex" aria-label="Страница" class="h-8 rounded-control border border-line bg-surface px-2 text-sm" @change="selectedId = null">
          <option v-for="(p, index) in draft.pages" :key="index" :value="index">{{ p.title }}</option>
        </select>
        <div class="flex rounded-control border border-line text-sm" role="radiogroup" aria-label="Устройство">
          <button
            v-for="(label, key) in { desktop: 'Компьютер', phone: 'Телефон' }"
            :key="key"
            type="button"
            role="radio"
            :aria-checked="device === key"
            class="px-3 py-1"
            :class="device === key ? 'bg-brand-100 text-brand-700' : 'hover:bg-brand-50'"
            @click="device = key"
          >
            {{ label }}
          </button>
        </div>
        <label class="flex items-center gap-2 text-sm text-ink-muted">
          Как видят
          <select v-model="phase" class="h-8 rounded-control border border-line bg-surface px-2 text-ink">
            <option v-for="(label, key) in PHASES" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <span class="ml-auto text-sm" :class="saveState === 'error' ? 'text-red-700' : 'text-ink-muted'" role="status">{{ SAVE_LABELS[saveState] }}</span>
        <a v-if="site?.published_at" :href="site.urls[0]" target="_blank" rel="noopener" class="text-sm text-brand-700 hover:underline">Открыть сайт</a>
        <UiButton variant="primary" :loading="publishing" :disabled="!canPublish && saveState === 'saved'" @click="publish">
          {{ site?.published_at ? (site.has_unpublished_changes ? 'Опубликовать изменения' : 'Опубликовано') : 'Опубликовать' }}
        </UiButton>
      </template>
    </header>

    <p v-if="loadError" role="alert" class="m-6 rounded-control bg-red-100 px-4 py-3 text-red-800">{{ loadError }}</p>
    <div v-else-if="!event || !site" class="p-6"><SkeletonPage :cards="3" /></div>

    <!-- Сайта ещё нет: выбор шаблона -->
    <div v-else-if="!draft" class="grid place-items-center overflow-y-auto p-6">
      <div class="grid w-full max-w-xl gap-5 rounded-card border border-line bg-surface p-8">
        <div>
          <h1 class="text-2xl font-bold">Соберите лендинг мероприятия</h1>
          <p class="mt-2 text-ink-muted">
            Начните с шаблона: блоки с датами, направлениями, регистрацией и итогами заполнятся из мероприятия сами.
            Тексты, порядок блоков и оформление можно поменять.
          </p>
        </div>
        <div class="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Шаблон">
          <button
            v-for="(template, key) in TEMPLATES"
            :key="key"
            type="button"
            role="radio"
            :aria-checked="templateType === key"
            class="rounded-card border p-4 text-left"
            :class="templateType === key ? 'border-brand-500 bg-brand-50' : 'border-line hover:bg-brand-50'"
            @click="templateType = key"
          >
            <span class="font-medium">{{ template.title }}</span>
            <span class="mt-1 block text-sm text-ink-muted">{{ template.blocks.length }} блоков</span>
          </button>
        </div>
        <UiButton variant="primary" @click="create">Создать сайт по шаблону</UiButton>
        <p class="text-sm text-ink-muted">Пока сайт не опубликован, по адресу {{ site.urls[0].replace('https://', '') }} открывается страница по шаблону.</p>
      </div>
    </div>

    <div v-else class="grid min-h-0 lg:grid-cols-[260px_minmax(0,1fr)_360px]">
      <!-- Список блоков -->
      <aside class="min-h-0 overflow-y-auto border-r border-line bg-surface p-3" aria-label="Блоки страницы">
        <p class="px-1 pb-2 text-xs font-semibold tracking-wide text-ink-muted uppercase">Блоки · {{ page.title }}</p>
        <ul class="grid gap-1">
          <li
            v-for="(block, index) in page.blocks"
            :key="block.id"
            class="group rounded-control border text-sm"
            :class="[
              selectedId === block.id ? 'border-brand-500 bg-brand-50' : 'border-transparent hover:bg-canvas',
              { 'opacity-40': dragging === index },
            ]"
            @dragover.prevent
            @drop="drop(index)"
          >
            <div class="flex items-center gap-1 px-1.5 py-1.5">
              <span
                draggable="true"
                class="cursor-grab px-1 text-ink-muted select-none"
                title="Перетащите, чтобы поменять порядок"
                aria-hidden="true"
                @dragstart="dragging = index"
                @dragend="dragging = null"
              >⋮⋮</span>
              <button type="button" class="min-w-0 flex-1 truncate text-left" :class="{ 'text-ink-muted line-through': block.hidden }" @click="scrollToBlock(block.id)">
                {{ getBlock(block.type).title }}
                <span v-if="erroredBlocks.has(block.id)" class="text-red-700" title="Есть ошибки">•</span>
              </button>
              <button
                type="button"
                class="rounded px-1 text-ink-muted hover:bg-surface hover:text-ink"
                :title="block.hidden ? 'Показать' : 'Скрыть'"
                :aria-label="block.hidden ? 'Показать блок' : 'Скрыть блок'"
                @click="block.hidden = !block.hidden"
              >
                {{ block.hidden ? '◌' : '◉' }}
              </button>
              <button type="button" class="rounded px-1 text-ink-muted hover:bg-surface hover:text-ink" title="Копия" aria-label="Копия блока" @click="duplicate(block)">⧉</button>
              <button type="button" class="rounded px-1 text-ink-muted hover:bg-red-50 hover:text-red-700" title="Удалить" aria-label="Удалить блок" @click="removing = block.id">×</button>
            </div>
            <div v-if="removing === block.id" class="flex flex-wrap items-center gap-2 border-t border-line px-2 py-1.5">
              Удалить блок?
              <UiButton size="sm" variant="danger" @click="remove(block)">Удалить</UiButton>
              <UiButton size="sm" variant="ghost" @click="removing = null">Нет</UiButton>
            </div>
          </li>
        </ul>
        <button type="button" class="mt-2 w-full rounded-control border border-dashed border-line px-3 py-2 text-sm text-brand-700 hover:bg-brand-50" @click="showPalette = true">
          + Добавить блок
        </button>
      </aside>

      <!-- Превью -->
      <section class="min-h-0 overflow-y-auto p-4" aria-label="Превью">
        <p v-if="notice" role="status" class="mx-auto mb-3 max-w-5xl rounded-control bg-green-100 px-4 py-2 text-sm text-green-800">{{ notice }}</p>
        <div
          v-if="errors.length && !selected"
          role="alert"
          class="mx-auto mb-3 max-w-5xl rounded-control bg-red-100 px-4 py-2 text-sm text-red-800"
        >
          <p class="font-medium">Сайт не сохранён:</p>
          <ul class="list-disc pl-5">
            <li v-for="(e, i) in errors.slice(0, 5)" :key="i">
              <button v-if="e.blockId" type="button" class="underline" @click="scrollToBlock(e.blockId)">{{ e.message }}</button>
              <span v-else>{{ e.message }}</span>
            </li>
          </ul>
        </div>
        <div
          class="mx-auto overflow-hidden bg-white shadow-sm ring-1 ring-line transition-[max-width]"
          :class="device === 'phone' ? 'max-w-[390px] rounded-[28px]' : 'max-w-5xl rounded-card'"
        >
          <SitePage :page="page" :theme="draft.theme" :data="previewData" :phase="phase" />
        </div>
        <p class="mx-auto mt-3 max-w-5xl text-center text-xs text-ink-muted">
          Нажмите на блок, чтобы настроить его. Заголовки и подписи правятся прямо на превью.
        </p>
      </section>

      <!-- Настройки -->
      <aside class="min-h-0 overflow-y-auto border-l border-line bg-surface p-4" aria-label="Настройки">
        <BlockSettings
          v-if="selected"
          :key="selected.id"
          :block="selected"
          :errors="blockErrors"
          @prop="(name, value) => (selected.props[name] = value)"
          @variant="(value) => (selected.variant = value)"
          @common="(name, value) => (selected.common[name] = value)"
          @close="selectedId = null"
        />
        <template v-else>
          <div class="mb-4 flex flex-wrap gap-1" role="tablist" aria-label="Настройки сайта">
            <button
              v-for="(label, key) in PANELS"
              :key="key"
              type="button"
              role="tab"
              :aria-selected="panel === key"
              class="rounded-full px-3 py-1 text-sm"
              :class="panel === key ? 'bg-brand-100 text-brand-700' : 'text-ink-muted hover:bg-brand-50'"
              @click="panel = key"
            >
              {{ label }}
            </button>
          </div>
          <ThemePanel v-if="panel === 'theme'" :theme="draft.theme" @change="(theme) => (draft.theme = theme)" />
          <SeoPanel v-else-if="panel === 'seo'" :seo="draft.seo" :event-title="event.title" @change="(seo) => (draft.seo = seo)" />
          <PagesPanel
            v-else-if="panel === 'pages'"
            :pages="draft.pages"
            :current="pageIndex"
            @select="(index) => ((pageIndex = index), (selectedId = null))"
            @add="addPage"
            @update="updatePage"
            @remove="removePage"
          />
          <DomainsPanel v-else-if="panel === 'domains'" :event-id="id" :site="site" @updated="(value) => (site = value)" />
          <template v-else-if="panel === 'versions'">
            <VersionsPanel ref="versionsPanel" :event-id="id" @restored="(value) => ((notice = 'Черновик возвращён к версии. Опубликуйте, чтобы изменения появились на сайте'), applySite(value))" />
            <div v-if="site.published_at" class="mt-6 border-t border-line pt-4 text-sm">
              <UiButton v-if="!confirmUnpublish" variant="ghost" @click="confirmUnpublish = true">Снять сайт с публикации</UiButton>
              <div v-else class="flex flex-wrap items-center gap-2">
                Посетители увидят страницу по шаблону. Снять?
                <UiButton size="sm" variant="danger" @click="unpublish">Снять</UiButton>
                <UiButton size="sm" variant="ghost" @click="confirmUnpublish = false">Отмена</UiButton>
              </div>
            </div>
          </template>
        </template>
      </aside>
    </div>

    <BlockPalette v-if="showPalette" @add="addBlock" @close="showPalette = false" />
  </div>
</template>
