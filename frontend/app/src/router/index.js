import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import SheetsView from '../views/SheetsView.vue'
import WorksView from '../views/WorksView.vue'
import EvaluationView from '../views/EvaluationView.vue'
import ViewerEvaluationView from '../views/ViewerEvaluationView.vue'

const NoAccessView = {
  template: `<div class="flex min-h-[60vh] items-center justify-center"><div class="text-center"><h1 class="mb-2 text-2xl font-bold text-gray-900 dark:text-gray-100">Доступ закрыт</h1><p class="text-gray-500 dark:text-gray-400">У вас нет роли для работы с этим приложением.</p><p class="mt-1 text-sm text-gray-400">Обратитесь к администратору для назначения роли Judge или Viewer.</p></div></div>`,
}

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/no-access', name: 'no-access', component: NoAccessView, meta: { public: true } },
  { path: '/', name: 'sheets', component: SheetsView },
  { path: '/sheets/:sheetId', name: 'works', component: WorksView, props: true },
  {
    path: '/sheets/:sheetId/works/:workId',
    name: 'evaluation',
    component: EvaluationView,
    props: true,
    meta: { requiresJudge: true },
  },
  {
    path: '/sheets/:sheetId/works/:workId/view',
    name: 'viewer-evaluation',
    component: ViewerEvaluationView,
    props: true,
    meta: { requiresViewer: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

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

  // Редирект при неверном режиме
  if (to.meta.requiresJudge && !auth.isJudge) {
    return { name: 'viewer-evaluation', params: to.params }
  }
  if (to.meta.requiresViewer && !auth.isViewer) {
    return { name: 'evaluation', params: to.params }
  }
})

export default router
