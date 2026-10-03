<script setup>
import { computed } from 'vue'
import { deadlineStatusLabel } from '../utils/competition'

const props = defineProps({
  competition: { type: Object, required: true },
})
// 颜色仅对应服务端截止状态，不推断报名是否已经开放。
const status = computed(() =>
  ['open', 'closed'].includes(props.competition.deadline_status)
    ? props.competition.deadline_status
    : 'unknown',
)
</script>

<template>
  <span class="deadline-status" :class="`deadline-status--${status}`">
    {{ deadlineStatusLabel(competition) }}
  </span>
</template>

<style scoped>
.deadline-status {
  display: inline-flex;
  max-width: 100%;
  padding: 5px 10px;
  border: 1px solid;
  border-radius: 7px;
  font-size: var(--type-small);
  font-weight: 600;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.deadline-status--open {
  color: var(--success, #166443);
  background: var(--success-surface, #eaf7ef);
  border-color: var(--border, #b9dec8);
}
.deadline-status--closed {
  color: var(--text-secondary, #475467);
  background: var(--surface, #f2f4f7);
  border-color: var(--border, #d0d5dd);
}
.deadline-status--unknown {
  color: var(--warning, #855300);
  background: var(--warning-surface, #fff5db);
  border-color: var(--border, #ebd39b);
}
</style>
