<template>
  <section class="welcome" aria-labelledby="welcome-title">
    <el-card shadow="never">
      <h1 id="welcome-title">前端工程已就绪</h1>
      <p>页面与功能将在后续阶段逐步接入。</p>
      <RouterLink class="primary-link" :to="{ name: 'competitions' }">
        查看赛事列表 →
      </RouterLink>
    </el-card>
  </section>
</template>
