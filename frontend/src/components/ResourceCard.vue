<script setup>
import { computed } from 'vue'
import { formatDate, safeExternalUrl } from '../utils/competition'
import { resourceCategories, resourceDirections } from '../services/resources'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  item: { type: Object, required: true },
  detailQuery: { type: Object, default: () => ({}) },
  idPrefix: { type: String, default: 'resource' },
})
const category = computed(() => resourceCategories.find((option) => option.value === props.item.category))
const direction = computed(() => resourceDirections.find((option) => option.value === props.item.direction))
const sourceUrl = computed(() => safeExternalUrl(props.item.url))
</script>

<template>
  <article class="editorial-card resource-card" :aria-labelledby="`${idPrefix}-${item.id}-title`">
    <p class="editorial-meta">
      <AppIcon :name="category?.icon || 'book'" :size="17" />
      {{ category?.label || '资源' }}
    </p>
    <h3 :id="`${idPrefix}-${item.id}-title`">
      <RouterLink :to="{ name: 'resource-detail', params: { id: item.id }, query: detailQuery }">
        {{ item.title }}
      </RouterLink>
    </h3>
    <div class="tag-row">
      <span class="tag">{{ direction?.label || '资源' }}</span>
      <span v-for="tag in item.tags" :key="tag" class="tag neutral">{{ tag }}</span>
    </div>
    <p class="resource-description">{{ item.description }}</p>
    <p class="resource-card-source">
      {{ item.source }} · 整理于 {{ formatDate(item.updatedAt) }}
    </p>
    <div class="resource-card-actions">
      <RouterLink class="more-link" :to="{ name: 'resource-detail', params: { id: item.id }, query: detailQuery }">
        查看详情 <AppIcon name="arrow" :size="16" />
      </RouterLink>
      <a v-if="sourceUrl" class="more-link" :href="sourceUrl" target="_blank" rel="noopener noreferrer">
        访问原文 ↗
      </a>
    </div>
  </article>
</template>
