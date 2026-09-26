<script setup>
import AppIcon from '../components/AppIcon.vue'
</script>

<template>
  <section class="not-found" aria-labelledby="not-found-title">
    <span class="not-found-orbit"><AppIcon name="spark" :size="45" /></span>
    <p class="not-found-number">404</p>
    <h1 id="not-found-title">这个页面还没有被发现</h1>
    <p>链接可能有误，或页面已被移动。回到熟悉的起点，继续探索吧。</p>
    <div class="not-found-actions">
      <RouterLink class="action-button" to="/">返回首页</RouterLink
      ><RouterLink
        class="action-button secondary"
        :to="{ name: 'competitions' }"
        >发现赛事</RouterLink
      >
    </div>
  </section>
</template>

<style scoped>
.not-found {
  text-align: center;
  padding: 70px 24px;
  border-radius: 18px;
  border: 1px solid #e0ebfa;
  background: linear-gradient(145deg, #f5f9ff, #eaf3ff);
}
.not-found-orbit {
  display: inline-flex;
  width: 86px;
  height: 86px;
  align-items: center;
  justify-content: center;
  border: 1px solid #caddfa;
  border-radius: 50%;
  color: #6c9eea;
  box-shadow: 0 0 0 14px #e1edff75;
}
.not-found-number {
  font-size: 90px;
  font-weight: 750;
  line-height: 1;
  color: #3278e4;
  margin: 30px 0 22px;
  letter-spacing: 6px;
}
.not-found h1 {
  font-size: 25px;
  margin: 0 0 16px;
}
.not-found > p:not(.not-found-number) {
  font-size: 13px;
  color: #8095b4;
  line-height: 1.8;
}
.not-found-actions {
  display: flex;
  justify-content: center;
  gap: 15px;
  margin-top: 26px;
}
</style>
