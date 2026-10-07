<script setup>
import { computed } from 'vue'
import { safeExternalUrl } from '../utils/competition'
const props = defineProps({ links: { type: Array, default: () => [] }, context: { type: String, default: '' } })
const sources = computed(() => {
  const seen = new Set()
  return props.links.flatMap(link => {
    const url = safeExternalUrl(link?.url)
    if (!url || !link?.label || seen.has(url)) return []
    seen.add(url)
    return [{ url, label: link.label }]
  })
})
</script>

<template>
  <span v-if="sources.length" class="research-field-links">
    <a v-for="source in sources" :key="source.url" :href="source.url"
       target="_blank" rel="noopener noreferrer" :aria-label="`${context}：${source.label}`">
      {{ source.label }} ↗
    </a>
  </span>
</template>
