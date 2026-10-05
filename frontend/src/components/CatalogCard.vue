<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  item: { type: Object, required: true },
  detailQuery: { type: Object, default: () => ({}) },
})
</script>

<template>
  <article class="competition-card catalog-card" :aria-labelledby="`catalog-${item.code}`">
    <div class="competition-card-body">
      <p class="editorial-meta">{{ item.code }} · {{ item.version }} 年目录</p>
      <div class="competition-card__header">
        <h2 :id="`catalog-${item.code}`">
          <RouterLink :to="{ name: 'catalog-detail', params: { code: item.code }, query: detailQuery }">
            {{ item.name }}
          </RouterLink>
        </h2>
      </div>
      <div class="tag-row">
        <span class="tag">目录等级 {{ item.grade || '未注明' }}</span>
        <span class="tag neutral">{{ item.levels || '范围待补充' }}</span>
      </div>
      <p class="competition-card__summary">{{ item.departments?.join('、') || '责任学院待补充' }}</p>
    </div>
    <div class="competition-card-aside">
      <span class="deadline-label">赛事档案</span>
      <span class="muted">{{ item.competition_count || 0 }} 条届次通知</span>
      <span class="muted">{{ item.resource_count || 0 }} 份学习资料</span>
      <RouterLink class="card-detail-link" :to="{ name: 'catalog-detail', params: { code: item.code }, query: detailQuery }">
        查看赛事资料 <AppIcon name="arrow" :size="16" />
      </RouterLink>
    </div>
  </article>
</template>
