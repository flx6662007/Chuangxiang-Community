<script setup>
import AppIcon from '../components/AppIcon.vue'
</script>

<template>
  <section class="information-center" aria-labelledby="information-title">
    <header class="page-heading">
      <span class="section-kicker">INFORMATION CENTER</span>
      <h1 id="information-title">信息中心</h1>
      <p>发现赛事讯息与项目招募，找到值得投入的方向。</p>
    </header>
    <nav class="information-tabs" aria-label="信息栏目">
      <RouterLink :to="{ name: 'competitions' }" exact-active-class="selected">
        <AppIcon name="trophy" :size="20" />赛事讯息
      </RouterLink>
      <RouterLink :to="{ name: 'research-projects' }" exact-active-class="selected">
        <AppIcon name="book" :size="20" />项目招募
      </RouterLink>
    </nav>
    <RouterView />
  </section>
</template>
