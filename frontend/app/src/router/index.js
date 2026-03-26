import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import SheetsView from '../views/SheetsView.vue'
import WorksView from '../views/WorksView.vue'
import EvaluationView from '../views/EvaluationView.vue'

const routes = [
  { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  { path: '/', name: 'sheets', component: SheetsView },
  { path: '/sheets/:sheetId', name: 'works', component: WorksView, props: true },
  {
    path: '/sheets/:sheetId/works/:workId',
    name: 'evaluation',
    component: EvaluationView,
    props: true,
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
})

export default router
