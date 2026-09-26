<script setup>
import AppIcon from '../components/AppIcon.vue'
</script>
<template>
  <el-container class="app-shell">
    <el-header class="app-header">
      <div class="app-header-inner">
        <RouterLink class="brand" to="/" aria-label="创享平台首页"
          ><span class="brand-mark"><AppIcon name="spark" :size="23" /></span
          ><span
            >创享<span class="brand-subtitle">科创与参赛社区</span></span
          ></RouterLink
        >
        <nav class="app-nav" aria-label="主导航">
          <RouterLink to="/" exact-active-class="is-active">首页</RouterLink>
          <RouterLink
            :to="{ name: 'competitions' }"
            :class="{ 'is-active': $route.path.startsWith('/competitions') }"
          >
            赛事中心
          </RouterLink>
          <RouterLink :to="{ name: 'account' }" exact-active-class="is-active"
            >我的账号</RouterLink
          >
        </nav>
        <RouterLink class="header-account" :to="{ name: 'account' }"
          ><AppIcon name="user" :size="16" /><span>账号中心</span></RouterLink
        >
      </div>
    </el-header>
    <el-main class="app-main">
      <RouterView />
    </el-main>
    <footer class="app-footer">
      <div>
        <span class="footer-brand">创享 · 让好想法找到起点</span
        ><span>创新俱乐部</span>
      </div>
      <p>赛事信息以官方通知为准</p>
    </footer>
  </el-container>
</template>
