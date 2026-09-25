<template>
  <el-container class="app-shell">
    <el-header class="app-header">
      <div class="app-header-inner">
        <RouterLink class="brand" to="/">创享平台</RouterLink>
        <nav class="app-nav" aria-label="主导航">
          <RouterLink to="/" exact-active-class="is-active">首页</RouterLink>
          <RouterLink :to="{ name: 'competitions' }" :class="{ 'is-active': $route.path.startsWith('/competitions') }">
            赛事列表
          </RouterLink>
          <RouterLink :to="{ name: 'account' }" exact-active-class="is-active">我的账号</RouterLink>
        </nav>
      </div>
    </el-header>
    <el-main class="app-main">
      <RouterView />
    </el-main>
  </el-container>
</template>
