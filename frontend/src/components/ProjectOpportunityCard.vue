<script setup>
import { computed } from 'vue'
import { formatDate, safeExternalUrl } from '../utils/competition'
const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, default: 1 },
})
const sourceUrl = computed(() => safeExternalUrl(props.item.sourceUrl))
</script>

<template>
  <article
    class="research-opportunity"
    :aria-labelledby="'project-' + item.id + '-title'"
  >
    <span class="research-opportunity-number">{{ String(index).padStart(2, '0') }}</span>
    <div class="research-opportunity-main">
      <p class="research-opportunity-unit">{{ item.unit || '官方科研线索' }}</p>
      <h3 :id="'project-' + item.id + '-title'">{{ item.title }}</h3>
      <p class="research-opportunity-summary preserve-lines">{{ item.summary }}</p>
      <p v-if="item.participation" class="research-opportunity-participation">{{ item.participation }}</p>
      <p v-if="item.evidenceNote" class="research-opportunity-evidence preserve-lines">{{ item.evidenceNote }}</p>
    </div>
    <div class="research-opportunity-meta">
      <p><span>原文日期</span><strong>{{ formatDate(item.date) }}</strong></p>
      <p><span>核查日期</span><strong>{{ formatDate(item.verifiedOn) }}</strong></p>
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
      <span v-else>官方链接待核对</span>
    </div>
  </article>
</template>
