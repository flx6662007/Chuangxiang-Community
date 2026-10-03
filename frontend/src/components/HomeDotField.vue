<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const field = ref(null)
const canvas = ref(null)
const cell = 24
const size = 392
const half = size / 2
const influence = 148
const fadeStart = 122
const fadeEnd = 178

let host
let context
let media
let frame = 0
let lastTime = 0
let strength = 0
let targetStrength = 0
let pointer = { x: 0, y: 0 }

function resizeCanvas() {
  if (!canvas.value) return
  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  canvas.value.width = Math.round(size * ratio)
  canvas.value.height = Math.round(size * ratio)
  context = canvas.value.getContext('2d')
  context?.setTransform(ratio, 0, 0, ratio, 0, 0)
  if (strength > 0) schedule()
}

function draw(x, y) {
  if (!context) return
  context.clearRect(0, 0, size, size)
  if (strength < 0.005) return

  const left = Math.round(x - half)
  const top = Math.round(y - half)
  canvas.value.style.transform = `translate3d(${left}px, ${top}px, 0)`
  canvas.value.style.opacity = `${strength}`

  const firstColumn = Math.floor((x - fadeEnd - cell / 2) / cell)
  const lastColumn = Math.ceil((x + fadeEnd - cell / 2) / cell)
  const firstRow = Math.floor((y - fadeEnd - cell / 2) / cell)
  const lastRow = Math.ceil((y + fadeEnd - cell / 2) / cell)

  for (let row = firstRow; row <= lastRow; row += 1) {
    for (let column = firstColumn; column <= lastColumn; column += 1) {
      const baseX = column * cell + cell / 2
      const baseY = row * cell + cell / 2
      const dx = baseX - x
      const dy = baseY - y
      const distance = Math.hypot(dx, dy)
      if (distance >= fadeEnd) continue

      const falloff = Math.max(0, 1 - distance / influence)
      const push = 44 * Math.pow(falloff, 0.8) * strength
      const angle = (column * 73 + row * 131) * 2.39996
      const directionX = distance > 0 ? dx / distance : Math.cos(angle)
      const directionY = distance > 0 ? dy / distance : Math.sin(angle)
      const edgeFade = distance <= fadeStart ? 1 : (fadeEnd - distance) / (fadeEnd - fadeStart)
      const alpha = edgeFade * (0.42 + falloff * 0.28)

      context.beginPath()
      context.arc(baseX - left + directionX * push, baseY - top + directionY * push, 1.25, 0, Math.PI * 2)
      context.fillStyle = `rgba(141, 184, 228, ${alpha})`
      context.fill()
    }
  }
}

function tick(now) {
  frame = 0
  const dt = lastTime ? Math.min((now - lastTime) / 1000, 1 / 30) : 1 / 60
  lastTime = now
  const speed = targetStrength ? 14 : 8
  strength += (targetStrength - strength) * (1 - Math.exp(-speed * dt))
  if (Math.abs(targetStrength - strength) < 0.005) strength = targetStrength

  const box = host.getBoundingClientRect()
  const x = pointer.x - box.left
  const y = pointer.y - box.top
  field.value.style.setProperty('--dot-x', `${x}px`)
  field.value.style.setProperty('--dot-y', `${y}px`)
  field.value.style.setProperty('--dot-hole-inner', `${fadeStart * strength}px`)
  field.value.style.setProperty('--dot-hole-outer', `${fadeEnd * strength}px`)
  draw(x, y)

  if (strength !== targetStrength) frame = requestAnimationFrame(tick)
  else lastTime = 0
}

function schedule() {
  if (!frame) frame = requestAnimationFrame(tick)
}

function move(event) {
  if (!context || media.matches || event.pointerType !== 'mouse') return
  pointer = { x: event.clientX, y: event.clientY }
  targetStrength = 1
  schedule()
}

function hide() {
  targetStrength = 0
  if (strength > 0) schedule()
}

function scroll() {
  if (strength > 0) schedule()
}

function mediaChange() {
  if (!media.matches) return
  cancelAnimationFrame(frame)
  frame = 0
  strength = 0
  targetStrength = 0
  field.value.style.setProperty('--dot-hole-inner', '0px')
  field.value.style.setProperty('--dot-hole-outer', '0px')
  context?.clearRect(0, 0, size, size)
  canvas.value.style.opacity = '0'
}

onMounted(() => {
  host = field.value.parentElement
  media = window.matchMedia('(prefers-reduced-motion: reduce), (hover: none)')
  resizeCanvas()
  host.addEventListener('pointermove', move, { passive: true })
  host.addEventListener('pointerleave', hide)
  media.addEventListener('change', mediaChange)
  window.addEventListener('resize', resizeCanvas)
  window.addEventListener('scroll', scroll, { passive: true })
  window.addEventListener('blur', hide)
  document.addEventListener('visibilitychange', hide)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  host?.removeEventListener('pointermove', move)
  host?.removeEventListener('pointerleave', hide)
  media?.removeEventListener('change', mediaChange)
  window.removeEventListener('resize', resizeCanvas)
  window.removeEventListener('scroll', scroll)
  window.removeEventListener('blur', hide)
  document.removeEventListener('visibilitychange', hide)
})
</script>

<template>
  <div ref="field" class="home-dot-field" aria-hidden="true">
    <div class="home-dot-field__grid" />
    <canvas ref="canvas" class="home-dot-field__motion" />
  </div>
</template>

<style scoped>
.home-dot-field { position: absolute; inset: 0; z-index: 1; overflow: hidden; pointer-events: none; }
.home-dot-field__grid {
  position: absolute; inset: 0;
  background-image: radial-gradient(circle, #8db8e46b 0 1px, #5b8abe20 1.3px, transparent 2.2px);
  background-size: 24px 24px;
  -webkit-mask-image: radial-gradient(circle at var(--dot-x, -1000px) var(--dot-y, -1000px), transparent 0 var(--dot-hole-inner, 0px), #000 var(--dot-hole-outer, 0px));
  mask-image: radial-gradient(circle at var(--dot-x, -1000px) var(--dot-y, -1000px), transparent 0 var(--dot-hole-inner, 0px), #000 var(--dot-hole-outer, 0px));
}
.home-dot-field__motion { position: absolute; top: 0; left: 0; width: 392px; height: 392px; opacity: 0; will-change: transform; }
@media (prefers-reduced-motion: reduce), (hover: none) { .home-dot-field__motion { display: none; } }
</style>
