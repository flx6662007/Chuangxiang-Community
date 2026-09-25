<template>
  <section class="welcome" aria-labelledby="welcome-title">
    <el-card shadow="never">
      <h1 id="welcome-title">发现适合你的竞赛</h1>
      <p>在创享集中查阅赛事信息、报名要求和通知来源。组队等功能将逐步开放。</p>
      <RouterLink class="primary-link" :to="{ name: 'competitions' }">
        查看赛事列表 →
      </RouterLink>
    </el-card>
  </section>
</template>
