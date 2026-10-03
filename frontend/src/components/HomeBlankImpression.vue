<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
const root = ref(null)
let host, media, timer, frame = 0, point
function hide() {
  clearTimeout(timer)
  cancelAnimationFrame(frame)
  frame = 0
  root.value?.style.setProperty('--impression-opacity', '0')
}
function paint() {
  frame = 0
  const box = host.getBoundingClientRect()
  const text = host.querySelector('.hero-lead').getBoundingClientRect()
  if (point.y < text.bottom + 16 || point.y > box.bottom - 18) { hide(); return }
  const x = Math.max(72, Math.min(box.width - 72, point.x - box.left))
  const y = point.y - box.top
  root.value.style.left = `${x}px`
  root.value.style.top = `${y}px`
  root.value.style.setProperty('--impression-opacity', '.65')
  clearTimeout(timer)
  timer = setTimeout(hide, 650)
}
function move(event) {
  if (media.matches || event.pointerType !== 'mouse') return
  point = { x: event.clientX, y: event.clientY }
  if (!frame) frame = requestAnimationFrame(paint)
}
onMounted(() => {
  host = root.value.parentElement
  media = matchMedia('(prefers-reduced-motion: reduce), (hover: none)')
  host.addEventListener('pointermove', move, { passive: true })
  host.addEventListener('pointerleave', hide)
  media.addEventListener('change', hide)
  window.addEventListener('scroll', hide, { passive: true })
  window.addEventListener('blur', hide)
  document.addEventListener('visibilitychange', hide)
})
onBeforeUnmount(() => {
  hide()
  host?.removeEventListener('pointermove', move)
  host?.removeEventListener('pointerleave', hide)
  media?.removeEventListener('change', hide)
  window.removeEventListener('scroll', hide)
  window.removeEventListener('blur', hide)
  document.removeEventListener('visibilitychange', hide)
})
</script>
<template>
  <svg ref="root" class="blank-impression" viewBox="0 0 144 32" aria-hidden="true" focusable="false">
    <path d="M 4 9 C 34 9 40 23 72 23 S 110 9 140 9" />
  </svg>
</template>
<style scoped>
.blank-impression { position: absolute; width: 144px; height: 32px; transform: translate(-50%, -50%); pointer-events: none; opacity: var(--impression-opacity, 0); transition: left 150ms ease-out, top 150ms ease-out, opacity 400ms ease; mask-image: linear-gradient(90deg, transparent, #000 30%, #000 70%, transparent); }
.blank-impression path { fill: none; stroke: #8aafd5; stroke-width: 1; }
@media (prefers-reduced-motion: reduce), (hover: none) { .blank-impression { display: none; } }
</style>
