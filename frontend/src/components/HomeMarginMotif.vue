<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
defineProps({ kind: { type: String, default: 'star' } })
const root = ref(null)
let section, media, frame = 0, previous = 0
const state = { x: 0, y: 0, r: 0, vx: 0, vy: 0, vr: 0, tx: 0, ty: 0, tr: 0 }
function paint() {
  root.value.style.transform = `translate(${state.x}px, ${state.y}px) rotate(${state.r}deg)`
}
function tick(now) {
  const dt = Math.min((now - previous) / 1000, 1 / 30)
  previous = now
  let moving = false
  for (const axis of ['x', 'y', 'r']) {
    for (let i = 0; i < 2; i++) {
      state[`v${axis}`] += ((state[`t${axis}`] - state[axis]) * 170 - state[`v${axis}`] * 20) * dt / 2
      state[axis] += state[`v${axis}`] * dt / 2
    }
    if (Math.abs(state[axis] - state[`t${axis}`]) > .01 || Math.abs(state[`v${axis}`]) > .02) moving = true
    else { state[axis] = state[`t${axis}`]; state[`v${axis}`] = 0 }
  }
  paint()
  frame = moving ? requestAnimationFrame(tick) : 0
}
function start() {
  if (!frame && !media.matches) { previous = performance.now(); frame = requestAnimationFrame(tick) }
}
function move(event) {
  if (media.matches || event.pointerType !== 'mouse') return
  // Measure the fixed holder, never the moving artwork.
  const rect = root.value.parentElement.getBoundingClientRect()
  const dx = event.clientX - rect.left - rect.width / 2
  const dy = event.clientY - rect.top - rect.height / 2
  const distance = Math.hypot(dx, dy)
  const strength = Math.max(0, 1 - distance / 280)
  state.tx = -dx / Math.max(distance, 40) * strength * 13
  state.ty = -dy / Math.max(distance, 40) * strength * 13
  state.tr = Math.max(-1, Math.min(1, dx / 65)) * strength * 24
  start()
}
function release() { state.tx = state.ty = state.tr = 0; start() }
function reset() {
  cancelAnimationFrame(frame); frame = 0
  Object.keys(state).forEach(key => { state[key] = 0 })
  paint()
}
onMounted(() => {
  section = root.value.closest('section')
  media = matchMedia('(prefers-reduced-motion: reduce), (hover: none)')
  section.addEventListener('pointermove', move, { passive: true })
  section.addEventListener('pointerleave', release)
  media.addEventListener('change', reset)
  window.addEventListener('scroll', reset, { passive: true })
  window.addEventListener('blur', reset)
  document.addEventListener('visibilitychange', reset)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  section?.removeEventListener('pointermove', move)
  section?.removeEventListener('pointerleave', release)
  media?.removeEventListener('change', reset)
  window.removeEventListener('scroll', reset)
  window.removeEventListener('blur', reset)
  document.removeEventListener('visibilitychange', reset)
})
</script>
<template>
  <span class="margin-motif" aria-hidden="true">
    <svg ref="root" viewBox="0 0 64 64" focusable="false">
      <path v-if="kind === 'star'" d="M32 5 Q35 29 59 32 Q35 35 32 59 Q29 35 5 32 Q29 29 32 5Z" fill="none" stroke="currentColor" stroke-width="1.5" />
      <g v-else transform="rotate(-25 32 32)"><ellipse cx="23" cy="32" rx="14" ry="20" fill="currentColor" opacity=".75"/><ellipse cx="41" cy="32" rx="14" ry="20" fill="none" stroke="currentColor" stroke-width="1.5"/></g>
    </svg>
  </span>
</template>
<style scoped>
.margin-motif { position: absolute; left: 65%; top: 40px; width: 46px; height: 46px; color: var(--accent, #82a8d9); pointer-events: none; }
.margin-motif svg { width: 100%; height: 100%; overflow: visible; }
@media (max-width: 900px) { .margin-motif { left: 70%; top: -20px; width: 32px; height: 32px; } }
@media (max-width: 480px) { .margin-motif { left: auto; right: 8px; top: -28px; width: 26px; height: 26px; } }
</style>
