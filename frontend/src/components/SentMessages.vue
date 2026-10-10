<script setup>
import { computed } from 'vue'
const props = defineProps({ messages: { type: Array, default: () => [] } })
const latest = computed(() => props.messages.at(-1))
</script>

<template>
  <aside v-if="latest" class="sent-messages" aria-label="已发送的指令">
    <div class="sent-latest" aria-live="polite"><strong>你刚刚说</strong><p>{{ latest }}</p></div>
    <details v-if="messages.length > 1">
      <summary>查看之前的指令（{{ messages.length - 1 }}）</summary>
      <ol><li v-for="(text, index) in messages.slice(0, -1)" :key="index">{{ text }}</li></ol>
    </details>
  </aside>
</template>

<style scoped>
.sent-messages { min-width: 0; padding: 16px 20px; border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 12px; background: var(--bg-secondary); color: var(--text-primary); }
.sent-latest strong, summary { font-size: var(--type-small); color: var(--text-secondary); }
.sent-latest p { margin: 8px 0 0; max-height: 9em; overflow-y: auto; }
.sent-latest p, li { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
summary { margin-top: 12px; cursor: pointer; padding-block: 6px; }
ol { max-height: 240px; overflow-y: auto; margin-bottom: 0; padding-left: 24px; }
li + li { margin-top: 12px; }
</style>
