<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import EditorialHeroVisual from '../components/EditorialHeroVisual.vue'

const route = useRoute()
const page = computed(() => {
  if (route.name === 'research-projects') return {
    first: '走进', second: '真正的研究。',
    description: '从官方科研线索出发，探索适合自己的研究方向。',
  }
  if (['resources', 'resource-detail'].includes(route.name)) return {
    first: '查找', second: '学习与工具资源。',
    description: '按方向与类型查找资源。当前清单为前端示例，内容及来源请逐项核对。',
  }
  return {
    first: '发现', second: '值得参加的赛事。',
    description: '从真实收录的赛事出发，找到值得投入的下一步。',
  }
})
</script>

<template>
  <section class="information-center" aria-labelledby="information-title">
    <header class="information-hero">
      <div class="information-hero-inner">
        <EditorialHeroVisual
          v-if="route.name === 'competitions' || route.name === 'research-projects'"
          :variant="route.name === 'competitions' ? 'competition' : 'research'"
        />
        <h1 id="information-title">
          {{ page.first }}<br />
          <span>{{ page.second }}</span>
        </h1>
        <p>{{ page.description }}</p>
      </div>
    </header>
    <div class="information-content">
      <RouterView />
    </div>
  </section>
</template>
