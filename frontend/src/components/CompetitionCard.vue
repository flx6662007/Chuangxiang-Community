<script setup>
import { computed } from 'vue'
import {
  formatDate,
  summaryDeadline,
  levelLabels,
  participationLabels,
  safeExternalUrl,
  officialText,
  officialUnknown,
  teamSizeLabel,
  formatUpdatedAt,
} from '../utils/competition'
import AppIcon from './AppIcon.vue'
import DeadlineStatusBadge from './DeadlineStatusBadge.vue'

const props = defineProps({
  competition: { type: Object, required: true },
  detailQuery: { type: Object, default: () => ({}) },
  detailEnabled: { type: Boolean, default: true },
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
          <RouterLink v-if="detailEnabled" :to="detailLink">{{ competition.title }}</RouterLink>
          <span v-else>{{ competition.title }}</span>
        </h2>
        <span class="competition-card__edition">{{ competition.edition }}</span>
      </div>
      <div class="tag-row">
        <span v-if="competition.category" class="tag">{{
          competition.category.name
        }}</span
        ><span class="tag warm">{{
          competition.level === 'unknown' ? officialUnknown : levelLabels[competition.level] || officialUnknown
        }}</span
        ><span class="tag neutral">{{
          competition.participation_type === 'unknown' ? officialUnknown : participationLabels[competition.participation_type] || officialUnknown
        }}</span>
      </div>
      <p><DeadlineStatusBadge :competition="competition" /></p>
      <p class="competition-card__summary">
        {{ officialText(competition.summary) }}
      </p>
      <p class="competition-card__organizer">
        <AppIcon name="building" :size="14" /><span class="competition-card__organizer-text">{{
          officialText(competition.organizer)
        }}</span>
      </p>
      <p class="competition-card__eligibility">
        <span>参赛资格：</span>{{ officialText(competition.eligibility) }}
      </p>
      <p class="competition-card__team-size">参赛人数：{{ teamSizeLabel(competition) }}</p>
      <div
        v-if="competition.tags?.length"
        class="tag-row competition-card__tags"
      >
        <span v-for="tag in competition.tags" :key="tag.id"
          ># {{ tag.name }}</span
        >
      </div>
      <footer class="competition-card__source">
        <span>原文发布：{{ sourcePublishedAt === '未注明' ? officialUnknown : sourcePublishedAt }}</span>
        <span>最近核验：{{ competition.last_verified_at ? formatUpdatedAt(competition.last_verified_at) : '尚未记录' }}</span
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
      ><RouterLink v-if="detailEnabled" class="card-detail-link" :to="detailLink"
        >查看详情<AppIcon name="arrow" :size="16"
      /></RouterLink>
    </div>
  </article>
</template>

<style scoped>
.competition-card__summary,
.competition-card__organizer-text,
.competition-card__eligibility {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.competition-card__organizer-text {
  min-width: 0;
  overflow-wrap: anywhere;
}
.competition-card__organizer :deep(svg) {
  flex-shrink: 0;
}
.competition-card__source > * {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
}
.competition-card__eligibility,
.competition-card__team-size {
  margin: 7px 0 0;
  color: var(--text-secondary, #667085);
  font-size: var(--type-small);
  line-height: var(--leading-body);
  overflow-wrap: anywhere;
}
</style>
