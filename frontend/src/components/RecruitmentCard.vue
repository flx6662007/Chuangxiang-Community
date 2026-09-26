<script setup>
import { recruitmentDeadline } from '../utils/teams'
import { label, optionNames } from '../utils/teams'
import { formatUpdatedAt } from '../utils/competition'
import AppIcon from './AppIcon.vue'
defineProps({ item: Object, detailQuery: Object })
const statusLabels = {
  open: '正在招募',
  full: '名额已满',
  paused: '暂缓招募',
  closed: '已结束',
  expired: '已到期',
  unavailable: '不可申请',
}
</script>
<template>
  <article class="recruitment-card">
    <span class="recruitment-emblem"><AppIcon name="users" :size="28" /></span>
    <div class="recruitment-card-copy">
      <div class="tag-row">
        <span class="tag" :class="{ neutral: !item.is_open }">{{
          statusLabels[item.status] || '不可申请'
        }}</span
        ><span class="muted">{{ item.competition.edition }}</span>
      </div>
      <h2>
        <RouterLink
          :to="{
            name: 'recruitment-detail',
            params: { id: item.id },
            query: detailQuery,
          }"
          >{{ item.competition.title }} ·
          {{
            item.required_roles?.length
              ? optionNames(item.required_roles)
              : '参赛招募'
          }}</RouterLink
        >
      </h2>
      <p>
        {{ label(item.foundation_requirement) }} ·
        {{ label(item.weekly_effort) }} · {{ label(item.collaboration_mode) }}
      </p>
      <div class="tag-row">
        <span
          v-for="skill in item.required_skills"
          :key="skill.code"
          class="tag neutral"
          >{{ skill.name }}</span
        >
      </div>
      <p class="timestamp">
        到期：{{ formatUpdatedAt(recruitmentDeadline(item))
        }}<span v-if="item.last_edited_at">
          · 编辑：{{ formatUpdatedAt(item.last_edited_at) }}</span
        >
      </p>
    </div>
    <div class="recruitment-card-aside">
      <strong>{{ item.remaining_slots }}</strong
      ><span>剩余名额</span
      ><RouterLink
        :to="{
          name: 'recruitment-detail',
          params: { id: item.id },
          query: detailQuery,
        }"
        >查看招募 →</RouterLink
      >
    </div>
  </article>
</template>
