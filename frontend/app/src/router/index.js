/**
 * Маршрутизатор приложения с защитой маршрутов.
 *
 * Маршруты:
 *   /login          — страница входа (публичная)
 *   /no-access      — заглушка при отсутствии роли
 *   /               — список оценочных листов (Judge); перенаправляет на /results для Viewer-only
 *   /sheets/:id     — список работ в листе (Judge)
 *   /sheets/:id/works/:id       — оценка работы (только Judge)
 *   /results        — список оценочных листов (Viewer/Admin)
 *   /results/aggregate         — сводный рейтинг по нескольким листам (Viewer/Admin)
 *   /results/sheets/:id         — список работ (Viewer/Admin)
 *   /results/sheets/:id/works/:id — просмотр оценок (Viewer/Admin)
 *
 * Навигационный гард (beforeEach):
 *   1. Редиректит авторизованного пользователя со страницы логина
 *   2. Проверяет наличие токена и загружает профиль пользователя
 *   3. Проверяет роль и перенаправляет при несоответствии
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import SheetsView from '../views/SheetsView.vue'
import WorksView from '../views/WorksView.vue'
import EvaluationView from '../views/EvaluationView.vue'
import ViewerEvaluationView from '../views/ViewerEvaluationView.vue'
import AggregateResultsView from '../views/AggregateResultsView.vue'

/** Заглушка для пользователей без роли Judge или Viewer */
const NoAccessView = {
  template: `<div class="flex min-h-[60vh] items-center justify-center"><div class="text-center"><h1 class="mb-2 text-2xl font-bold text-gray-900 dark:text-gray-100">Доступ закрыт</h1><p class="text-gray-500 dark:text-gray-400">У вас нет роли для работы с этим приложением.</p><p class="mt-1 text-sm text-gray-400">Обратитесь к администратору для назначения роли Judge или Viewer.</p></div></div>`,
}

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/no-access', name: 'no-access', component: NoAccessView, meta: { public: true } },
  // Judge routes
  { path: '/', name: 'sheets', component: SheetsView },
  { path: '/sheets/:sheetId', name: 'works', component: WorksView, props: true },
  {
    path: '/sheets/:sheetId/works/:workId',
    name: 'evaluation',
    component: EvaluationView,
    props: true,
    meta: { requiresJudge: true },
  },
  // Viewer/Admin routes (просмотр результатов)
  {
    path: '/results',
    name: 'results-sheets',
    component: SheetsView,
    meta: { viewerMode: true, requiresViewer: true },
  },
  {
    path: '/results/aggregate',
    name: 'results-aggregate',
    component: AggregateResultsView,
    meta: { viewerMode: true, requiresViewer: true },
  },
  {
    path: '/results/sheets/:sheetId',
    name: 'results-works',
    component: WorksView,
    props: true,
    meta: { viewerMode: true, requiresViewer: true },
  },
  {
    path: '/results/sheets/:sheetId/works/:workId',
    name: 'results-evaluation',
    component: ViewerEvaluationView,
    props: true,
    meta: { viewerMode: true, requiresViewer: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // Редирект авторизованных пользователей со страницы логина
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'sheets' }
  }

  if (to.meta.public) return

  if (!auth.isAuthenticated) return '/login'

  if (!auth.user) {
    try {
      await auth.fetchUser()
    } catch {
      auth.logout()
      return '/login'
    }
  }

  // Проверка доступа по роли
  if (!auth.hasAccess) return { name: 'no-access' }

  // Если нет роли Judge — перенаправляем с judge-маршрутов на просмотр результатов
  if (!auth.isJudge && (to.name === 'sheets' || to.name === 'works')) {
    if (to.name === 'sheets') return { name: 'results-sheets' }
    if (to.name === 'works') return { name: 'results-works', params: to.params }
  }

  // Проверка ролевых требований маршрута
  if (to.meta.requiresJudge && !auth.isJudge) {
    return { name: 'sheets' }
  }
  if (to.meta.requiresViewer && !auth.isViewer) {
    return { name: 'sheets' }
  }
})

export default router
