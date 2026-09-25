<script setup>
import { computed, ref } from 'vue'

import CompetitionCard from '../components/CompetitionCard.vue'
import { mockCompetitions } from '../mocks/competitions.js'

const currentPage = ref(1)
const pageSize = 5

const visibleCompetitions = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return mockCompetitions.slice(start, start + pageSize)
})
</script>

<template>
  <section class="competition-page" aria-labelledby="competition-title">
    <header class="page-heading">
      <h1 id="competition-title">赛事列表</h1>
      <p>发现赛事机会，了解报名与参赛信息。</p>
    </header>

    <div class="competition-list" aria-live="polite">
      <CompetitionCard
        v-for="competition in visibleCompetitions"
        :key="competition.id"
        :competition="competition"
      />
    </div>

    <el-pagination
      v-model:current-page="currentPage"
      class="competition-pagination"
      :page-size="pageSize"
      :total="mockCompetitions.length"
      layout="prev, pager, next"
      background
      aria-label="赛事列表分页"
    />
  </section>
</template>
