import { createRouter, createWebHistory } from 'vue-router'
import { publicResourceQuery } from '../utils/library'

import AppLayout from '../layouts/AppLayout.vue'
import WelcomeView from '../views/WelcomeView.vue'
import CompetitionListView from '../views/CompetitionListView.vue'
import InformationCenterView from '../views/InformationCenterView.vue'
import CompetitionDetailView from '../views/CompetitionDetailView.vue'
import AccountView from '../views/AccountView.vue'
import NotFoundView from '../views/NotFoundView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
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

router.beforeEach((to) => {
  if (['resources', 'resource-detail'].includes(to.name) && Object.hasOwn(to.query, 'preview')) {
    return { name: to.name, params: to.params, query: publicResourceQuery(to.query), hash: to.hash, replace: true }
  }
})

export default router
