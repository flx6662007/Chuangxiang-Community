<script setup>
import AppIcon from '../components/AppIcon.vue'
</script>
<template>
  <el-container class="app-shell" :class="{ 'is-home': $route.name === 'home' }">
    <el-header class="app-header">
      <div class="app-header-inner">
        <RouterLink class="brand" to="/" aria-label="创享平台首页"
          ><span class="brand-mark"><AppIcon name="spark" :size="23" /></span
          ><span
            >创享<span class="brand-subtitle">CHUANGXIANG</span></span
          ></RouterLink
        >
        <nav class="app-nav" aria-label="主导航">
          <RouterLink to="/" exact-active-class="is-active">发现</RouterLink>
          <RouterLink
            :to="{ name: 'competitions' }"
            :class="{ 'is-active': $route.name === 'competitions' || $route.name === 'competition-detail' }"
          >
            赛事
          </RouterLink>
          <RouterLink :to="{ name: 'research-projects' }" :class="{ 'is-active': $route.name === 'research-projects' }">科研</RouterLink>
          <RouterLink
            to="/teams"
            :class="{ 'is-active': $route.path.startsWith('/teams') }"
            >组队</RouterLink
          >
          <a v-if="$route.name === 'home'" href="#ai">AI</a>
        </nav>
        <div class="header-actions">
          <RouterLink to="/account/teams" exact-active-class="is-active">我的组队</RouterLink>
          <RouterLink to="/account/notifications" exact-active-class="is-active">通知</RouterLink>
          <RouterLink class="header-account" :to="{ name: 'account' }"
            ><AppIcon name="user" :size="16" /><span>账户</span></RouterLink
          >
        </div>
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
      <p>赛事与项目参与要求以官方说明为准</p>
    </footer>
  </el-container>
</template>
