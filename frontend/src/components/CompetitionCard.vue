<script setup>
import { computed } from 'vue'
import {
  formatDate,
  summaryDeadline,
  levelLabels,
  participationLabels,
  safeExternalUrl,
} from '../utils/competition'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  competition: { type: Object, required: true },
  detailQuery: { type: Object, default: () => ({}) },
})
const deadline = computed(() => summaryDeadline(props.competition))
const sourcePublishedAt = computed(() =>
  formatDate(props.competition.primary_source?.source_published_on),
)
const sourceUrl = computed(() =>
  safeExternalUrl(props.competition.primary_source?.source_url),
)
const detailLink = computed(() => ({
  name: 'competition-detail',
  params: { id: props.competition.id },
  query: props.detailQuery,
}))
</script>

<template>
  <article
    class="competition-card"
    :aria-labelledby="`competition-${competition.id}-title`"
  >
    <span class="competition-emblem" aria-hidden="true"
      ><AppIcon name="trophy" :size="31"
    /></span>
    <div class="competition-card-body">
      <div class="competition-card__header">
        <h2 :id="`competition-${competition.id}-title`">
          <RouterLink :to="detailLink">{{ competition.title }}</RouterLink>
        </h2>
        <span class="competition-card__edition">{{ competition.edition }}</span>
      </div>
      <div class="tag-row">
        <span v-if="competition.category" class="tag">{{
          competition.category.name
        }}</span
        ><span class="tag warm">{{
          levelLabels[competition.level] || '范围未注明'
        }}</span
        ><span class="tag neutral">{{
          participationLabels[competition.participation_type] ||
          '参赛形式未说明'
        }}</span>
      </div>
      <p class="competition-card__summary">
        {{ competition.summary || '简介待补充' }}
      </p>
      <p class="competition-card__organizer">
        <AppIcon name="building" :size="14" />{{
          competition.organizer || '主办方未注明'
        }}
      </p>
      <div
        v-if="competition.tags?.length"
        class="tag-row competition-card__tags"
      >
        <span v-for="tag in competition.tags" :key="tag.id"
          ># {{ tag.name }}</span
        >
      </div>
      <footer class="competition-card__source">
        <span>来源发布：{{ sourcePublishedAt }}</span
        ><a
          v-if="sourceUrl"
          :href="sourceUrl"
          target="_blank"
          rel="noopener noreferrer"
          >{{ competition.primary_source?.source_name || '通知原文' }} ↗</a
        >
      </footer>
    </div>
    <div class="competition-card-aside">
      <span class="deadline-label"
        ><AppIcon name="calendar" :size="16" />{{ deadline.label }}</span
      ><strong>{{ deadline.value }}</strong
      ><RouterLink class="card-detail-link" :to="detailLink"
        >查看详情<AppIcon name="arrow" :size="16"
      /></RouterLink>
    </div>
  </article>
</template>
