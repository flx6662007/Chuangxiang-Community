<script setup>
import { computed } from 'vue'

const props = defineProps({
  competition: {
    type: Object,
    required: true,
  },
})

const registrationDeadline = computed(() => formatDate(props.competition.registration_deadline))
const submissionDeadline = computed(() => formatDate(props.competition.submission_deadline))
const sourcePublishedAt = computed(() => formatDate(props.competition.source_published_at))

function formatDate(value) {
  if (!value) return '暂未公布'

  // Treat YYYY-MM-DD as a calendar date in the user's locale, without UTC date shifting.
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value)

  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    ...(dateOnly ? {} : { hour: '2-digit', minute: '2-digit' }),
  }).format(date)
}
</script>

<template>
  <el-card class="competition-card" shadow="never">
    <article :aria-labelledby="`competition-${competition.id}-title`">
      <header class="competition-card__header">
        <h2 :id="`competition-${competition.id}-title`">{{ competition.title }}</h2>
        <span class="competition-card__edition">{{ competition.edition }}</span>
      </header>

      <dl class="competition-card__dates">
        <div>
          <dt>报名截止</dt>
          <dd>{{ registrationDeadline }}</dd>
        </div>
        <div>
          <dt>作品提交截止</dt>
          <dd>{{ submissionDeadline }}</dd>
        </div>
      </dl>

      <footer class="competition-card__source">
        <span>来源发布时间：{{ sourcePublishedAt }}</span>
        <a :href="competition.source_url" target="_blank" rel="noopener noreferrer">
          查看来源
        </a>
      </footer>
    </article>
  </el-card>
</template>

<style scoped>
.competition-card {
  border-radius: 10px;
}

.competition-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.competition-card__header h2 {
  margin: 0;
  color: #243047;
  font-size: 18px;
  line-height: 1.5;
}

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
}

.competition-card__source {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 14px;
  border-top: 1px solid #eef0f3;
  color: #667085;
  font-size: 13px;
}

.competition-card__source a {
  flex: none;
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
