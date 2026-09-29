<script setup>
import { recruitmentDeadline } from '../utils/teams'
import { label, optionNames } from '../utils/teams'
import { formatUpdatedAt } from '../utils/competition'
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
  <article v-reveal class="recruitment-card" :aria-labelledby="`recruitment-${item.id}-title`">
    <div class="recruitment-card-copy">
      <div class="tag-row">
        <span class="tag recruitment-status" :class="{ neutral: !item.is_open }">{{
          statusLabels[item.status] || '不可申请'
        }}</span
        ><span class="muted">{{ item.competition.edition }}</span>
      </div>
      <h2 :id="`recruitment-${item.id}-title`">
        <RouterLink
          :to="{
            name: 'recruitment-detail',
            params: { id: item.id },
            query: detailQuery,
          }"
          >{{ item.competition.title }}</RouterLink
        >
      </h2>
      <dl class="recruitment-needs">
        <div><dt>寻找角色</dt><dd>{{ optionNames(item.required_roles) }}</dd></div>
        <div><dt>所需技能</dt><dd>{{ optionNames(item.required_skills) }}</dd></div>
      </dl>
      <p class="recruitment-commitment">
        {{ label(item.foundation_requirement) }} ·
        {{ label(item.weekly_effort) }} · {{ label(item.collaboration_mode) }}
      </p>
      <p class="timestamp">
        到期：{{ formatUpdatedAt(recruitmentDeadline(item))
        }}<span v-if="item.last_edited_at">
          · 编辑：{{ formatUpdatedAt(item.last_edited_at) }}</span
        >
      </p>
    </div>
    <div class="recruitment-card-aside">
      <dl class="recruitment-members">
        <div><dt>已有成员基数</dt><dd>{{ item.current_existing_member_count ?? '—' }} <span>人</span></dd></div>
        <div><dt>本轮已加入</dt><dd>{{ item.joined_member_count ?? '—' }} <span>人</span></dd></div>
        <div class="recruitment-slots"><dt>剩余名额</dt><dd>{{ item.remaining_slots }} <span>人</span></dd></div>
      </dl>
      <RouterLink class="recruitment-detail-link"
        :to="{
          name: 'recruitment-detail',
          params: { id: item.id },
          query: detailQuery,
        }"
        >查看招募 <span aria-hidden="true">↗</span></RouterLink
      >
    </div>
  </article>
</template>
