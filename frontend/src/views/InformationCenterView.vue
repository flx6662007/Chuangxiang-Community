<script setup>
import AppIcon from '../components/AppIcon.vue'
</script>

<template>
  <section class="information-center" aria-labelledby="information-title">
    <header class="page-heading">
      <span class="section-kicker">INFORMATION CENTER</span>
      <h1 id="information-title">信息中心</h1>
      <p>查阅赛事讯息、项目招募与长期学习资源，找到值得投入的方向。</p>
    </header>
    <nav class="information-tabs" aria-label="信息栏目">
      <RouterLink :to="{ name: 'competitions' }" exact-active-class="selected">
        <AppIcon name="trophy" :size="20" />赛事讯息
      </RouterLink>
      <RouterLink :to="{ name: 'research-projects' }" exact-active-class="selected">
        <AppIcon name="book" :size="20" />项目招募
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
  </section>
</template>
