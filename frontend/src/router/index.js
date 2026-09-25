import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '../layouts/AppLayout.vue'
import WelcomeView from '../views/WelcomeView.vue'
import CompetitionListView from '../views/CompetitionListView.vue'

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
      ],
    },
  ],
})

export default router
