<script setup>
import { computed } from 'vue'
import { safeExternalUrl } from '../utils/competition'
import ResearchFieldLinks from './ResearchFieldLinks.vue'
const props = defineProps({
  item: { type: Object, required: true },
})
const sourceUrl = computed(() => safeExternalUrl(props.item.sourceUrl))
const fieldLinks = computed(() => props.item.details?.fieldLinks || {})
const facts = computed(() => {
  const details = props.item.details || {}
  const recruitment = details.recruitment || {}
  return [
    ['direction', '研究方向', details.direction], ['location', '地点', details.location], ['achievements', '研究成果', details.achievements],
    ['roles', '招募对象', recruitment.roles], ['eligibility', '申请条件', recruitment.eligibility],
    ['work', '具体工作', recruitment.work], ['commitment', '时间投入', recruitment.commitment],
    ['scope', '申请范围', recruitment.scope], ['cohort', '招募批次', recruitment.cohort],
    ['deadline', '截止时间', recruitment.deadline], ['status', '批次状态', recruitment.status],
    ['recruitment', '招募信息', ''],
  ].filter(([key, , value]) => (typeof value === 'string' && value.trim()) || fieldLinks.value[key]?.length)
})
</script>

<template>
  <article
    class="research-opportunity"
    :aria-labelledby="'project-' + item.id + '-title'"
  >
    <div class="research-opportunity-main">
      <p class="research-opportunity-unit">{{ item.unit || '官方科研线索' }}</p>
      <h3 :id="'project-' + item.id + '-title'">{{ item.title }}</h3>
      <p class="research-opportunity-summary preserve-lines">{{ item.summary }}<ResearchFieldLinks :links="fieldLinks.summary" :context="`${item.title}研究简介`" /></p>
      <dl v-if="facts.length" class="research-opportunity-facts">
        <div v-for="[key, label, value] in facts" :key="key">
          <dt>{{ label }}</dt><dd :class="{ 'links-only': !value }">{{ value }}<ResearchFieldLinks :links="fieldLinks[key]" :context="`${item.title}${label}`" /></dd>
        </div>
      </dl>
    </div>
    <div class="research-opportunity-action">
      <a
        v-if="sourceUrl"
        :href="sourceUrl"
        target="_blank"
        rel="noopener noreferrer"
        :aria-label="`查看${item.title}的官方说明`"
        >官方说明 ↗</a
      >
      <span v-else>暂无来源链接</span>
    </div>
  </article>
</template>
