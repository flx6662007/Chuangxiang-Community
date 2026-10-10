<script setup>
import wordmark from '../assets/xiaochuang-ai.png'

defineProps({
  variant: { type: String, default: 'inline' },
})
</script>

<template>
  <span class="xiaochuang-logo" :class="`xiaochuang-logo--${variant}`" role="img" aria-label="小创AI"
    :style="{ '--wordmark': `url(${wordmark})` }">
    <img :src="wordmark" alt="" aria-hidden="true" width="2172" height="724" />
  </span>
</template>

<style scoped>
.xiaochuang-logo { display: inline-block; width: 4.8em; max-width: 100%; aspect-ratio: 3; vertical-align: middle; flex-shrink: 0; }
.xiaochuang-logo img { display: block; width: 100%; height: 100%; object-fit: contain; }
.xiaochuang-logo--nav { width: 94px; }
.xiaochuang-logo--heading { width: clamp(210px, 24vw, 300px); }
.xiaochuang-logo--hero { width: 100%; background: currentColor; mask: var(--wordmark) center / contain no-repeat; }
.xiaochuang-logo--hero img { visibility: hidden; }
:global([data-theme="dark"]) .xiaochuang-logo:not(.xiaochuang-logo--hero) img { filter: brightness(0) invert(1); opacity: .92; }
@media (max-width: 640px) { .xiaochuang-logo--nav { width: 82px; } }
@media (forced-colors: active) {
  .xiaochuang-logo { background: CanvasText; mask: var(--wordmark) center / contain no-repeat; }
  .xiaochuang-logo img { visibility: hidden; }
}
</style>
