<script setup>
import { computed } from 'vue'
import { formatDate, safeExternalUrl } from '../utils/competition'
const props = defineProps({ item: { type: Object, required: true } })
const sourceUrl = computed(() => safeExternalUrl(props.item.sourceUrl))
</script>

<template>
  <article
    class="editorial-card"
    :aria-labelledby="'project-' + item.id + '-title'"
  >
    <p class="editorial-meta">{{ item.unit || '官方科研线索' }}</p>
    <h3 :id="'project-' + item.id + '-title'">{{ item.title }}</h3>
    <p class="preserve-lines">{{ item.summary }}</p>
    <p v-if="item.participation" class="editorial-participation">
      {{ item.participation }}
    </p>
    <p v-if="item.evidenceNote" class="field-hint preserve-lines">
      {{ item.evidenceNote }}
    </p>
    <p class="timestamp">
      <span>原文日期：{{ formatDate(item.date) }}</span
      ><br />
      <span>核查日期：{{ formatDate(item.verifiedOn) }}</span>
    </p>
    <a
      v-if="sourceUrl"
      class="more-link"
      :href="sourceUrl"
      target="_blank"
      rel="noopener noreferrer"
      >查阅官方说明 ↗</a
    >
    <p v-else class="field-hint">官方链接待核对。</p>
  </article>
</template>
