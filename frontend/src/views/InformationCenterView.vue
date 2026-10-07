<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import EditorialHeroVisual from '../components/EditorialHeroVisual.vue'

const route = useRoute()
const page = computed(() => {
  if (route.name === 'research-projects') return {
    first: '走进', second: '真正的研究',
    description: '',
  }
  if (['resources', 'resource-detail'].includes(route.name)) return {
    first: '查找', second: '学习与工具资源',
    description: '规则、赛题、教程与工具，按赛事集中查阅。',
  }
  return {
    first: '发现', second: '值得参加的赛事',
    description: '浏览赛事目录、届次通知与学习资料。',
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
        <p v-if="page.description">{{ page.description }}</p>
      </div>
    </header>
    <div class="information-content">
      <RouterView />
    </div>
  </section>
</template>
