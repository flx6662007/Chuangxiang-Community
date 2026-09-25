import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '../layouts/AppLayout.vue'
import WelcomeView from '../views/WelcomeView.vue'
import CompetitionListView from '../views/CompetitionListView.vue'
import CompetitionDetailView from '../views/CompetitionDetailView.vue'
import AccountView from '../views/AccountView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
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
          name: 'competitions',
          component: CompetitionListView,
        },
        {
          path: 'competitions/:id(\\d+)',
          name: 'competition-detail',
          component: CompetitionDetailView,
        },
        {
          path: 'account',
          name: 'account',
          component: AccountView,
        },
      ],
    },
  ],
})

export default router
