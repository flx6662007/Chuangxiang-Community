<script setup>
import { computed } from 'vue'
import { formatDate, formatDeadline, formatUpdatedAt, levelLabels, participationLabels, safeExternalUrl } from '../utils/competition'

const props = defineProps({
  competition: {
    type: Object,
    required: true,
  },
  detailQuery: {
    type: Object,
    default: () => ({}),
  },
})

const registrationDeadline = computed(() => formatDeadline(props.competition, 'registration_deadline'))
const sourcePublishedAt = computed(() => formatDate(props.competition.primary_source?.source_published_on))
const sourceUrl = computed(() => safeExternalUrl(props.competition.primary_source?.source_url))
const detailLink = computed(() => ({ name: 'competition-detail', params: { id: props.competition.id }, query: props.detailQuery }))
</script>

<template>
  <el-card class="competition-card" shadow="never">
    <article :aria-labelledby="`competition-${competition.id}-title`">
      <div class="tag-row">
        <span v-if="competition.category" class="tag">{{ competition.category.name }}</span>
        <span class="tag neutral">{{ levelLabels[competition.level] || '范围未注明' }}</span>
        <span class="tag neutral">{{ participationLabels[competition.participation_type] || '参赛形式未说明' }}</span>
      </div>
      <header class="competition-card__header">
        <h2 :id="`competition-${competition.id}-title`"><RouterLink :to="detailLink">{{ competition.title }}</RouterLink></h2>
        <span class="competition-card__edition">{{ competition.edition }}</span>
      </header>
      <p class="competition-card__summary">{{ competition.summary || '简介待补充' }}</p>
      <p class="competition-card__organizer">主办方：{{ competition.organizer || '未注明' }}</p>
      <dl class="competition-card__dates">
        <div>
          <dt>报名截止</dt>
          <dd>{{ registrationDeadline }}</dd>
        </div>
        <div>
          <dt>作品提交截止</dt>
          <dd><RouterLink :to="detailLink">在赛事详情中查看 →</RouterLink></dd>
        </div>
      </dl>
      <div v-if="competition.tags?.length" class="tag-row competition-card__tags"><span v-for="tag in competition.tags" :key="tag.id"># {{ tag.name }}</span></div>
      <p class="competition-card__published">来源发布日期：{{ sourcePublishedAt }}</p>
      <footer class="competition-card__source">
        <RouterLink :to="detailLink">查看详情 →</RouterLink>
        <a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noopener noreferrer">
          {{ competition.primary_source?.source_name || '通知原文' }} ↗
        </a>
      </footer>
      <p class="timestamp">信息更新：{{ formatUpdatedAt(competition.updated_at) }}</p>
    </article>
  </el-card>
</template>

<style scoped>
.competition-card {
  border-radius: 12px;
}

.competition-card article { display: flex; flex-direction: column; min-height: 345px; }
.competition-card a { color: #2452a1; text-decoration: none; text-underline-offset: 3px; }
.competition-card a:hover { text-decoration: underline; }

.competition-card__header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

.competition-card__header h2 {
  margin: 0;
  color: #243047;
  font-size: 21px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.competition-card__header h2 a { color: #243047; }
.competition-card__header h2 a:hover { color: #2563eb; }
.competition-card__summary { margin: 14px 0; line-height: 1.7; overflow-wrap: anywhere; }
.competition-card__organizer { margin: 0; font-size: 14px; line-height: 1.7; overflow-wrap: anywhere; }
.competition-card__tags { margin-bottom: 12px; color: #667085; font-size: 12px; }
.competition-card__published { margin: 0 0 12px; color: #667085; font-size: 12px; }

.competition-card__edition {
  flex: none;
  color: #667085;
  font-size: 14px;
}

.competition-card__dates {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin: 22px 0;
}

.competition-card__dates div {
  min-width: 0;
}

.competition-card__dates dt {
  margin-bottom: 6px;
  color: #667085;
  font-size: 13px;
}

.competition-card__dates dd {
  margin: 0;
  color: #344054;
  font-size: 14px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.competition-card__source {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid #eef0f3;
  color: #667085;
  font-size: 13px;
}

.competition-card__source a {
  overflow-wrap: anywhere;
  color: #2563eb;
  text-underline-offset: 3px;
}

@media (max-width: 520px) {
  .competition-card__header,
  .competition-card__source {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }
}
</style>
