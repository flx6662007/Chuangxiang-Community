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
  const x = Math.max(96, Math.min(box.width - 96, point.x - box.left))
  const y = point.y - box.top
  root.value.style.left = `${x}px`
  root.value.style.top = `${y}px`
  const edge = Math.min(1, (point.y - text.bottom - 16) / 28, (box.bottom - 18 - point.y) / 32)
  root.value.style.setProperty('--impression-opacity', `${Math.max(0, edge) * .95}`)
  clearTimeout(timer)
  timer = setTimeout(hide, 800)
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
  <span ref="root" class="blank-impression" aria-hidden="true"><i /></span>
</template>
<style scoped>
.blank-impression {
  position: absolute; width: 184px; height: 82px; transform: translate(-50%, -50%);
  pointer-events: none; opacity: var(--impression-opacity, 0);
  transition: left 160ms ease-out, top 160ms ease-out, opacity 450ms ease;
  background: radial-gradient(ellipse at 50% 45%, #03091288, #06101b22 48%, transparent 72%);
}
.blank-impression::before, .blank-impression i {
  content: ''; position: absolute; inset: 10px 9px; border-radius: 50%;
  background: radial-gradient(ellipse at center, transparent 60%, #88bcff 65%, #5899e5aa 68%, transparent 74%);
  mask-image: conic-gradient(from 10deg, transparent 0deg 90deg, #000 130deg 190deg, transparent 245deg 360deg);
  transform: rotate(-18deg); filter: blur(.8px);
}
.blank-impression i { filter: blur(5px); opacity: .5; }
@media (prefers-reduced-motion: reduce), (hover: none) { .blank-impression { display: none; } }
</style>
