<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'

const root = ref(null)
const links = [
  { id: 'ai', title: '小创', description: '找赛事 · 找队友 · 查资料', kind: 'ai' },
  { id: 'newsletters', title: '创享快讯', kind: 'news' },
]
let media
let frame = 0
let previous = 0
let nodes = []
let observer
let visible = false
let phase = 0
let engagement = 0
let engagementTarget = 0
const clamp = (value, limit = 1) => Math.max(-limit, Math.min(limit, value))
const states = links.map(() => ({ x: 0, y: 0, tx: 0, ty: 0, vx: 0, vy: 0 }))

// Four continuous curves: a flat, gently asymmetric silhouette, never a goo filter.
function outline(x, y, index) {
  const bias = index ? -7 : 7
  return `M ${147 + x} 10 C ${236 + x} ${-3 + y}, 294 ${65 + bias}, 290 ${145 + y} C 288 ${230 + y}, ${235 - bias} 290, ${151 - x} 289 C ${63 - x} 298, 5 ${239 - bias}, 10 ${153 - y} C 4 ${66 - y}, ${57 + bias} 16, ${147 + x} 10 Z`
}
function paint() {
  nodes.forEach((node, i) => {
    const { x, y, vx, vy } = states[i]
    const idle = media?.matches ? 0 : 1 - engagement
    const angle = phase * Math.PI * 2 / (i ? 8 : 6.5) + i * 1.7
    const floatX = i ? Math.sin(angle) * 3.5 * idle : 0
    const floatY = Math.sin(angle + (i ? .7 : 0)) * 4 * idle
    // Keep the link hit area fixed while its visible contents float.
    node.querySelector('.liquid-label').style.translate = `${floatX}px ${floatY}px`
    node.querySelector('.liquid-surface').style.transform = `translate(${x * .5 + floatX}px, ${y * .5 + floatY}px) rotate(${x * .11}deg) scale(${1 + Math.sin(angle) * .022 * idle}, ${1 + Math.sin(angle + 1.1) * .018 * idle})`
    // Velocity adds a brief stretch; it decays when the pointer stops.
    node.querySelector('.liquid-surface path').setAttribute('d', outline(
      x + clamp(vx * .035, 4) + Math.sin(angle) * 5 * idle,
      y + clamp(vy * .035, 4) + Math.cos(angle) * 5 * idle, i))
  })
}
function tick(now) {
  const dt = Math.min((now - previous) / 1000 || 1 / 60, 1 / 30)
  previous = now
  phase += dt
  engagement += (engagementTarget - engagement) * (1 - Math.exp(-dt * 5))
  states.forEach(s => {
    // Small integration steps keep the spring stable on slower frames.
    for (let step = 0; step < 2; step++) {
      for (const axis of ['x', 'y']) {
        const velocity = `v${axis}`
        s[velocity] += ((s[`t${axis}`] - s[axis]) * 230 - s[velocity] * 23) * dt / 2
        s[axis] += s[velocity] * dt / 2
      }
    }
  })
  paint()
  frame = requestAnimationFrame(tick)
}
function start() {
  if (!frame && visible && !document.hidden && !media?.matches) {
    previous = performance.now()
    frame = requestAnimationFrame(tick)
  }
}
function move(event) {
  if (!visible || media?.matches || event.pointerType !== 'mouse') return
  const hits = nodes.map(node => {
    const rect = node.getBoundingClientRect()
    const dx = event.clientX - (rect.left + rect.width / 2)
    const dy = event.clientY - (rect.top + rect.height / 2)
    const distance = Math.hypot(dx, dy)
    const radius = rect.width * .47
    return { dx, dy, radius, strength: Math.max(0, 1 - Math.max(0, distance - radius) / 130) }
  })
  const index = hits[0].strength >= hits[1].strength ? 0 : 1
  const hit = hits[index]
  const hero = root.value.closest('.home-hero').getBoundingClientRect()
  const inHero = event.clientX >= hero.left && event.clientX <= hero.right && event.clientY >= hero.top && event.clientY <= hero.bottom
  const breezeX = inHero ? clamp((event.clientX - hero.left) / hero.width * 2 - 1) * 8 : 0
  const breezeY = inHero ? clamp((event.clientY - hero.top) / hero.height * 2 - 1) * 6 : 0
  engagementTarget = Math.max(hit.strength, inHero ? .3 : 0)
  const gain = 30 * hit.strength * hit.strength
  states[index].tx = clamp(hit.dx / hit.radius) * gain
  states[index].ty = clamp(hit.dy / hit.radius) * gain
  states[1 - index].tx = -states[index].tx * .18
  states[1 - index].ty = -states[index].ty * .18
  states.forEach((state, i) => {
    state.tx += breezeX * (1 - hit.strength) * (i ? .75 : 1)
    state.ty += breezeY * (1 - hit.strength) * (i ? 1 : .75)
  })
}
function release() {
  engagementTarget = 0
  states.forEach(s => { s.tx = 0; s.ty = 0 })
}
function syncPlayback() {
  cancelAnimationFrame(frame)
  frame = 0
  release()
  if (media?.matches) {
    engagement = 0
    states.forEach(s => { s.x = s.y = s.vx = s.vy = 0 })
    paint()
  }
  start()
}
function navigate(event, id) {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return
  const section = document.getElementById(id)
  if (!section) return
  event.preventDefault()
  section.scrollIntoView({ behavior: media?.matches ? 'instant' : 'smooth', block: 'start' })
  // Move keyboard context along with the viewport, without adding a permanent tab stop.
  section.setAttribute('tabindex', '-1')
  section.focus({ preventScroll: true })
  section.addEventListener('blur', () => section.removeAttribute('tabindex'), { once: true })
}
onMounted(() => {
  nodes = [...root.value.querySelectorAll('.liquid-link')]
  media = window.matchMedia('(prefers-reduced-motion: reduce)')
  media.addEventListener('change', syncPlayback)
  document.addEventListener('visibilitychange', syncPlayback)
  document.addEventListener('pointermove', move, { passive: true })
  document.documentElement.addEventListener('pointerleave', release)
  window.addEventListener('blur', release)
  window.addEventListener('scroll', release, { passive: true })
  observer = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    syncPlayback()
  })
  observer.observe(root.value)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  observer?.disconnect()
  media?.removeEventListener('change', syncPlayback)
  document.removeEventListener('visibilitychange', syncPlayback)
  document.removeEventListener('pointermove', move)
  document.documentElement.removeEventListener('pointerleave', release)
  window.removeEventListener('blur', release)
  window.removeEventListener('scroll', release)
})
</script>

<template>
  <nav ref="root" class="liquid-links" aria-label="发现页快捷入口">
    <a v-for="(link, index) in links" :key="link.id" :href="`#${link.id}`"
      class="liquid-link" :class="`liquid-link--${link.kind}`"
      @click="navigate($event, link.id)">
      <svg class="liquid-surface" viewBox="0 0 300 300" aria-hidden="true" focusable="false">
        <path :d="outline(0, 0, index)" />
      </svg>
      <span class="liquid-label">
        <svg v-if="index === 0" class="liquid-icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M16 2c2 9 5 12 14 14-9 2-12 5-14 14C14 21 11 18 2 16 11 14 14 11 16 2Z" fill="currentColor" /></svg>
        <svg v-else class="liquid-icon" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M7 6h18a3 3 0 0 1 3 3v13a3 3 0 0 1-3 3H13l-7 4v-4a3 3 0 0 1-3-3V9a3 3 0 0 1 4-3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M10 12h12M10 18h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
        <strong>{{ link.title }}</strong>
        <small v-if="link.description">{{ link.description }}</small>
        <span class="liquid-arrow" aria-hidden="true">↗</span>
      </span>
    </a>
  </nav>
</template>

<style scoped>
.liquid-links { position: relative; width: min(100%, 480px); height: 400px; margin: auto; }
.liquid-link { position: absolute; display: grid; place-items: center; aspect-ratio: 1; color: var(--text-primary, #102742); border-radius: 44%; isolation: isolate; transition: scale 160ms ease; -webkit-tap-highlight-color: transparent; }
.liquid-link--ai { width: 60%; top: 0; left: 0; }
.liquid-link--news { width: 52%; bottom: 0; right: 0; }
.liquid-surface { transform-origin: 50% 50%; position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; z-index: -1; }
.liquid-surface path { fill: var(--illustration, #7fa9ed); transition: fill 220ms ease; }
.liquid-link--news path { fill: var(--illustration-soft, #c5d9e9); }
.liquid-link--news .liquid-icon path { fill: none; }
.liquid-label { display: flex; flex-direction: column; align-items: center; gap: 13px; pointer-events: none; }
.liquid-label small { font-size: clamp(11px, 1vw, 13px); line-height: 1.5; }
.liquid-label strong { font-size: clamp(20px, 1.85vw, 27px); font-weight: 600; letter-spacing: -.025em; }
.liquid-icon { width: 32px; height: 32px; }
.liquid-arrow { font-size: 24px; line-height: 1; transition: transform 300ms var(--motion-ease-out); }
.liquid-link:hover .liquid-surface path, .liquid-link:focus-visible .liquid-surface path { fill: var(--illustration-soft, #91b7f3); }
.liquid-link--news:hover .liquid-surface path, .liquid-link--news:focus-visible .liquid-surface path { fill: var(--illustration-soft, #d5e4ee); }
.liquid-link:is(:hover, :focus-visible) .liquid-arrow { transform: translate(3px, -3px); }
.liquid-link:focus-visible { outline: 2px solid var(--border, #eef6ff); outline-offset: 6px; }
.liquid-link:active { scale: .98; }
@media (min-width: 901px) and (max-width: 1200px) { .liquid-links { height: 350px; } }
@media (max-width: 900px) { .liquid-links { max-width: 430px; height: 350px; } }
@media (max-width: 640px) {
  .liquid-links { max-width: 360px; height: 240px; }
  .liquid-link--ai { width: 55%; }
  .liquid-link--news { width: 49%; }
  .liquid-label { gap: 9px; }
  .liquid-label strong { font-size: 19px; }
  .liquid-icon { width: 25px; height: 25px; }
  .liquid-arrow { font-size: 21px; }
}
@media (prefers-reduced-motion: reduce) { .liquid-link, .liquid-link * { transition: none; transform: none; scale: none; } }
</style>
