<script setup>
import { useRoute } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import BrandLogo from '../components/BrandLogo.vue'
import ThemeToggle from '../components/ThemeToggle.vue'
const route = useRoute()
const privateBeta = import.meta.env.VITE_PRIVATE_BETA === '1'
function revisitAi() {
  if (route.name === 'home' && route.hash === '#ai') {
    document.getElementById('ai')?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    })
  }
}
</script>
<template>
  <el-container
    class="app-shell"
    :class="{
      'is-home': $route.name === 'home',
      'is-editorial-page': ['competitions', 'catalog-detail', 'research-projects', 'resources', 'resource-detail', 'teams', 'recruitment-detail', 'recruitment-publish', 'recruitment-edit', 'account', 'my-teams', 'notifications', 'governance'].includes($route.name),
      'is-team-page': ['teams', 'recruitment-detail', 'recruitment-publish', 'recruitment-edit'].includes($route.name),
      'is-account-page': ['account', 'my-teams', 'notifications', 'governance'].includes($route.name),
    }"
  >
    <el-header class="app-header">
      <div class="app-header-inner">
        <RouterLink class="brand" to="/" aria-label="创享平台首页">
          <BrandLogo />
          <span>创享<span class="brand-subtitle">CHUANGXIANG</span></span>
        </RouterLink>
        <nav class="app-nav" aria-label="主导航">
          <RouterLink to="/" exact-active-class="is-active">发现</RouterLink>
          <RouterLink :to="{ name: 'home', hash: '#ai' }" @click="revisitAi">AI</RouterLink>
          <RouterLink
            :to="{ name: 'competitions' }"
            :class="{ 'is-active': ['competitions', 'catalog-detail', 'competition-detail'].includes($route.name) }"
          >
            赛事
          </RouterLink>
          <RouterLink :to="{ name: 'research-projects' }" :class="{ 'is-active': $route.name === 'research-projects' }">科研</RouterLink>
          <RouterLink :to="{ name: 'resources' }" :class="{ 'is-active': ['resources', 'resource-detail'].includes($route.name) }">资源</RouterLink>
          <RouterLink
            to="/teams"
            :class="{ 'is-active': $route.path.startsWith('/teams') }"
            >组队</RouterLink
          >
        </nav>
        <div class="header-actions">
          <ThemeToggle />
          <RouterLink to="/account/teams" exact-active-class="is-active">我的组队</RouterLink>
          <RouterLink to="/account/notifications" exact-active-class="is-active">通知</RouterLink>
          <RouterLink class="header-account" :to="{ name: 'account' }" :aria-label="privateBeta ? '内测账号' : '账户'"
            ><AppIcon name="user" :size="16" /><span>{{ privateBeta ? '内测账号' : '账户' }}</span></RouterLink
          >
        </div>
      </div>
    </el-header>
    <el-main class="app-main">
      <div v-if="privateBeta" class="private-beta-banner" role="note">邀请内测 · 使用分配的测试账号体验 AI 助手、组队和举报，操作记录仅用于本轮测试</div>
      <RouterView />
    </el-main>
    <footer class="app-footer">
      <div>
        <span class="footer-brand">创享 · 竞赛与科研信息</span
        ><span>创新俱乐部</span>
      </div>
      <p>比赛通知 · 学习资料 · 组队招募</p>
    </footer>
  </el-container>
</template>
<style scoped>
.private-beta-banner { padding: 10px 24px; text-align: center; font-size: 13px; color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
</style>
