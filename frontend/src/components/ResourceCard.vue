<script setup>
import { computed } from 'vue'
import { formatUpdatedAt, safeExternalUrl } from '../utils/competition'
import { resourceIcon } from '../utils/library'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  item: { type: Object, required: true },
  detailQuery: { type: Object, default: () => ({}) },
  idPrefix: { type: String, default: 'resource' },
})
const sourceUrl = computed(() => props.item.availability === 'unavailable' ? '' : safeExternalUrl(props.item.source_url))
</script>

<template>
  <article class="editorial-card resource-card" :aria-labelledby="`${idPrefix}-${item.id}-title`">
    <p class="editorial-meta">
      <AppIcon :name="resourceIcon(item.category)" :size="17" />
      {{ item.facts?.kind || item.category?.name || '学习资料' }}
    </p>
    <h3 :id="`${idPrefix}-${item.id}-title`">
      <RouterLink :to="{ name: 'resource-detail', params: { id: item.id }, query: detailQuery }">
        {{ item.title }}
      </RouterLink>
    </h3>
    <div class="tag-row">
      <span v-if="item.facts?.difficulty" class="tag">{{ item.facts.difficulty }}</span>
      <span v-if="item.facts?.language" class="tag neutral">{{ item.facts.language }}</span>
      <span v-if="item.facts?.access" class="tag neutral">{{ item.facts.access }}</span>
      <span v-for="direction in item.directions" :key="direction.code" class="tag">{{ direction.name }}</span>
      <span v-for="tag in item.tags" :key="tag.code" class="tag neutral">{{ tag.name }}</span>
      <span v-if="item.availability === 'unavailable'" class="tag warm">链接暂不可用</span>
    </div>
    <p v-if="item.description" class="resource-description">{{ item.description }}</p>
    <p class="resource-card-source">
      <template v-if="item.provider">{{ item.provider }} · </template>整理于 {{ formatUpdatedAt(item.updated_at) }}
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
