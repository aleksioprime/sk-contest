import { createRouter, createWebHistory } from 'vue-router'
import { setUnauthorizedHandler } from '@/api/http'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

export const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue'), meta: { public: true } },
  {
    path: '/auth/magic',
    name: 'magic-link',
    component: () => import('@/views/auth/MagicLinkView.vue'),
    meta: { public: true },
  },
  {
    path: '/evaluate/:token',
    name: 'anonymous-evaluation',
    component: () => import('@/views/judging/AnonymousEvaluationView.vue'),
    props: true,
    meta: { public: true },
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', name: 'home', redirect: { name: 'events' } },
      { path: 'events', name: 'events', component: () => import('@/views/events/EventsView.vue') },
      { path: 'events/new', name: 'event-new', component: () => import('@/views/events/EventCreateView.vue') },
      { path: 'events/:id', name: 'event', component: () => import('@/views/events/EventView.vue'), props: true },
      {
        path: 'events/:id/sheets/:sheetId/judge-cards',
        name: 'judge-cards',
        component: () => import('@/views/events/JudgeCardsView.vue'),
        props: true,
        meta: { print: true },
      },
      {
        path: 'events/:id/sheets/:sheetId',
        name: 'event-sheet',
        component: () => import('@/views/events/SheetView.vue'),
        props: true,
      },
      { path: 'judging', name: 'judging', component: () => import('@/views/judging/JudgeSheetsView.vue') },
      {
        path: 'judging/sheets/:id',
        name: 'judge-sheet',
        component: () => import('@/views/judging/JudgeWorksView.vue'),
        props: true,
      },
      {
        path: 'judging/evaluations/:id',
        name: 'judge-evaluation',
        component: () => import('@/views/judging/JudgeEvaluationView.vue'),
        props: true,
      },
      {
        path: 'events/:slug/apply',
        name: 'apply',
        component: () => import('@/views/applications/ApplyView.vue'),
        props: true,
      },
      { path: 'my/applications', name: 'my-applications', component: () => import('@/views/applications/MyApplicationsView.vue') },
      {
        path: 'my/applications/:id',
        name: 'application',
        component: () => import('@/views/applications/ApplicationView.vue'),
        props: true,
      },
      { path: 'system', name: 'system', component: () => import('@/views/HomeView.vue'), meta: { admin: true } },
      { path: 'ui', name: 'ui-kit', component: () => import('@/views/UiKitView.vue'), meta: { admin: true } },
      {
        path: 'admin/people',
        name: 'admin-people',
        component: () => import('@/views/admin/PeopleView.vue'),
        meta: { admin: true },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

/** Проверка доступа к маршруту. Вынесена отдельно, чтобы её можно было протестировать. */
const JUDGE_ROUTES = new Set(['judging', 'judge-sheet', 'judge-evaluation'])

export function resolveAccess(to, auth) {
  if (to.meta.public) return true
  if (!auth.isAuthenticated) return { name: 'login', query: { next: to.fullPath } }
  // Судье на мероприятии доступны только его оценочные листы
  if (auth.judgeMode && !JUDGE_ROUTES.has(to.name)) return { name: 'judging' }
  if (to.meta.admin && !auth.isAdmin) return { name: 'home' }
  return true
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.load()
  return resolveAccess(to, auth)
})

setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  auth.setUser(null)
  const current = router.currentRoute.value
  // До завершения первой навигации маршрута ещё нет: доступ решит beforeEach
  if (!current.matched.length || current.meta.public) return
  router.push({ name: 'login', query: { next: current.fullPath } })
})
