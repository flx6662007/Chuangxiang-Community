import { createRouter, createWebHistory } from 'vue-router'
import { publicResourceQuery } from '../utils/library'

import AppLayout from '../layouts/AppLayout.vue'
import WelcomeView from '../views/WelcomeView.vue'
import CompetitionListView from '../views/CompetitionListView.vue'
import InformationCenterView from '../views/InformationCenterView.vue'
import CompetitionDetailView from '../views/CompetitionDetailView.vue'
import AccountView from '../views/AccountView.vue'
import NotFoundView from '../views/NotFoundView.vue'

let releaseScrollHold

function holdScrollPosition() {
  releaseScrollHold?.()
  const shell = document.querySelector('.app-shell')
  if (!shell || window.scrollY === 0) return

  const body = document.body
  const previousMinHeight = body.style.minHeight
  // Lists briefly collapse into a loading message. Keep enough page height
  // for the current viewport so the browser cannot clamp its scroll position.
  body.style.minHeight = `${window.scrollY + window.innerHeight}px`

  const releaseWhenSafe = () => {
    if (shell.getBoundingClientRect().height >= window.scrollY + window.innerHeight - 1) {
      releaseScrollHold?.()
    }
  }
  const observer = new MutationObserver(releaseWhenSafe)
  observer.observe(shell, { childList: true, subtree: true })
  window.addEventListener('scroll', releaseWhenSafe, { passive: true })
  releaseScrollHold = () => {
    observer.disconnect()
    window.removeEventListener('scroll', releaseWhenSafe)
    body.style.minHeight = previousMinHeight
    releaseScrollHold = undefined
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    // Filters and pagination update the query on the current page. Keep the
    // reader's position; only a new page or anchor should move the viewport.
    if (to.path === from.path && to.hash === from.hash) return false
    if (to.hash) return { el: to.hash, top: 24 }
    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'home',
          component: WelcomeView,
        },
        {
          path: 'competitions',
          component: InformationCenterView,
          children: [
            { path: '', name: 'competitions', component: CompetitionListView },
            { path: 'catalog/:code', name: 'catalog-detail', component: () => import('../views/CatalogDetailView.vue') },
          ],
        },
        {
          path: 'research',
          component: InformationCenterView,
          children: [
            { path: '', name: 'research-projects', component: () => import('../views/ProjectListView.vue') },
            { path: ':id(\\d+)', name: 'research-detail', component: () => import('../views/ResearchDetailView.vue') },
          ],
        },
        {
          path: 'resources',
          component: InformationCenterView,
          children: [
            { path: '', name: 'resources', component: () => import('../views/ResourceCenterView.vue') },
            { path: ':id', name: 'resource-detail', component: () => import('../views/ResourceDetailView.vue') },
          ],
        },
        {
          path: 'competitions/:id(\\d+)',
          name: 'competition-detail',
          component: CompetitionDetailView,
        },
        {
          path: 'information',
          redirect: to => ({ name: 'competitions', query: to.query, hash: to.hash }),
        },
        {
          path: 'information/competitions',
          redirect: to => ({ name: 'competitions', query: to.query, hash: to.hash }),
        },
        {
          path: 'information/competitions/:id(\\d+)',
          redirect: to => ({ name: 'competition-detail', params: to.params, query: to.query, hash: to.hash }),
        },
        {
          path: 'information/projects',
          redirect: to => ({ name: 'research-projects', query: to.query, hash: to.hash }),
        },
        {
          path: 'information/resources',
          redirect: to => ({ name: 'resources', query: to.query, hash: to.hash }),
        },
        {
          path: 'information/resources/:id',
          redirect: to => ({ name: 'resource-detail', params: to.params, query: to.query, hash: to.hash }),
        },
        {
          path: 'account',
          name: 'account',
          component: AccountView,
        },
        {
          path: 'teams',
          name: 'teams',
          component: () => import('../views/TeamListView.vue'),
        },
        {
          path: 'teams/publish',
          name: 'recruitment-publish',
          component: () => import('../views/RecruitmentFormView.vue'),
        },
        {
          path: 'teams/:id(\\d+)/edit',
          name: 'recruitment-edit',
          component: () => import('../views/RecruitmentFormView.vue'),
        },
        {
          path: 'teams/:id(\\d+)',
          name: 'recruitment-detail',
          component: () => import('../views/RecruitmentDetailView.vue'),
        },
        {
          path: 'account/teams',
          name: 'my-teams',
          component: () => import('../views/MyTeamsView.vue'),
        },
        {
          path: 'account/notifications',
          name: 'notifications',
          component: () => import('../views/NotificationsView.vue'),
        },
        {
          path: 'account/governance',
          name: 'governance',
          component: () => import('../views/GovernanceView.vue'),
        },
        {
          path: ':pathMatch(.*)*',
          name: 'not-found',
          component: NotFoundView,
        },
      ],
    },
  ],
})

router.beforeEach((to, from) => {
  if (to.path === from.path && to.hash === from.hash && to.fullPath !== from.fullPath) {
    holdScrollPosition()
  } else {
    releaseScrollHold?.()
  }
})

router.beforeEach((to) => {
  if (['resources', 'resource-detail'].includes(to.name) && Object.hasOwn(to.query, 'preview')) {
    return { name: to.name, params: to.params, query: publicResourceQuery(to.query), hash: to.hash, replace: true }
  }
})

export default router
