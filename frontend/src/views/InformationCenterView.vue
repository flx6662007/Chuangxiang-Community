<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'

const route = useRoute()
const isEditorialPage = computed(() => ['competitions', 'research-projects'].includes(route.name))
const isResearch = computed(() => route.name === 'research-projects')
</script>

<template>
  <section class="information-center" aria-labelledby="information-title">
    <header v-if="isEditorialPage" class="information-hero">
      <div class="information-hero-inner">
        <p class="information-eyebrow">CHUANGXIANG / <em>Discover &amp; Create</em></p>
        <span class="information-index">{{ isResearch ? '02 / RESEARCH' : '01 / DISCOVER' }}</span>
        <h1 id="information-title">
          {{ isResearch ? '走进' : '发现' }}<br />
          <span>{{ isResearch ? '真正的研究。' : '值得参加的赛事。' }}</span>
        </h1>
        <p>{{ isResearch ? '从官方科研线索出发，探索适合自己的研究方向。' : '从真实收录的赛事出发，找到值得投入的下一步。' }}</p>
      </div>
    </header>
    <header v-else class="page-heading">
      <span class="section-kicker">INFORMATION CENTER</span>
      <h1 id="information-title">信息中心</h1>
      <p>查阅赛事讯息、科研线索与长期学习资源，找到值得投入的方向。</p>
    </header>
    <div class="information-content">
      <nav class="information-tabs" aria-label="信息栏目">
        <RouterLink :to="{ name: 'competitions' }" exact-active-class="selected">
          <AppIcon name="trophy" :size="20" />赛事讯息
        </RouterLink>
        <RouterLink :to="{ name: 'research-projects' }" exact-active-class="selected">
          <AppIcon name="book" :size="20" />科研线索
        </RouterLink>
        <RouterLink
          :to="{ name: 'resources' }"
          exact-active-class="selected"
          :class="{ selected: $route.name === 'resource-detail' }"
        >
          <AppIcon name="link" :size="20" />资源中心
        </RouterLink>
      </nav>
      <RouterView />
    </div>
  </section>
</template>
