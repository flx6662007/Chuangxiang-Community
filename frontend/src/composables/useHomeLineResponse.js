import { onBeforeUnmount, onMounted } from 'vue'

// Reuse existing separators. Only the line nearest the pointer responds.
export function useHomeLineResponse(root) {
  let lines = []
  let media
  let frame = 0
  let pointer
  let active
  let resizeObserver
  const curves = new Map()
  function syncSeparatorColors() {
    // Read each rule's theme colour before restoring its SVG replacement.
    lines.forEach(line => line.classList.remove('pointer-separator'))
    lines.forEach(line => line.style.setProperty('--separator-color', getComputedStyle(line).borderTopColor))
    lines.forEach(line => line.classList.add('pointer-separator'))
  }
  function flatten(line) {
    if (!line) return
    line.style.setProperty('--line-opacity', '0')
    const curve = curves.get(line)
    if (curve) draw(curve, curve.x ?? curve.width / 2, 0)
  }
  function draw(curve, x, depth) {
    const span = Math.min(90, x, curve.width - x)
    curve.x = x
    const d = `M 0 8 H ${x - span} C ${x - span * .45} 8 ${x - span * .4} ${8 + depth} ${x} ${8 + depth} S ${x + span * .45} 8 ${x + span} 8 H ${curve.width}`
    curve.path.setAttribute('d', d)
    curve.glowPath.setAttribute('d', d)
  }
  function clear() {
    cancelAnimationFrame(frame)
    frame = 0
    flatten(active)
    active = null
    pointer = null
  }
  function paint() {
    frame = 0
    if (!pointer) return
    let nearest
    let distance = 64
    let position = 0
    for (const line of lines) {
      const rect = line.getBoundingClientRect()
      const delta = Math.abs(pointer.y - rect.top)
      if (pointer.x >= rect.left && pointer.x <= rect.right && delta < distance) {
        nearest = line
        distance = delta
        position = pointer.x - rect.left
      }
    }
    if (active !== nearest) flatten(active)
    active = nearest
    if (active) {
      active.style.setProperty('--line-x', `${position}px`)
      const curve = curves.get(active)
      curve.width = active.getBoundingClientRect().width
      curve.svg.setAttribute('viewBox', `0 0 ${curve.width} 24`)
      curve.glow.setAttribute('viewBox', `0 0 ${curve.width} 24`)
      const x = Math.max(1, Math.min(curve.width - 1, position))
      draw(curve, x, (1 - distance / 64) * 6)
      active.style.setProperty('--line-opacity', `${(1 - distance / 64) * .8}`)
    }
  }
  function move(event) {
    if (media.matches || event.pointerType !== 'mouse') return
    pointer = { x: event.clientX, y: event.clientY }
    if (!frame) frame = requestAnimationFrame(paint)
  }
  onMounted(() => {
    lines = [...root.value.querySelectorAll('.start-here, .home-ai, .research-list, .briefing-row')]
    resizeObserver = new ResizeObserver(() => {
      curves.forEach(curve => {
        curve.width = curve.svg.parentElement.getBoundingClientRect().width
        curve.svg.setAttribute('viewBox', `0 0 ${curve.width} 24`)
      curve.glow.setAttribute('viewBox', `0 0 ${curve.width} 24`)
        draw(curve, curve.width / 2, 0)
      })
    })
    lines.forEach(line => {
      line.style.setProperty('--separator-color', getComputedStyle(line).borderTopColor)
      line.classList.add('pointer-separator')
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
      svg.classList.add('separator-curve')
      svg.setAttribute('aria-hidden', 'true')
      svg.setAttribute('focusable', 'false')
      svg.setAttribute('preserveAspectRatio', 'none')
      svg.append(path)
      const glow = svg.cloneNode(true)
      glow.classList.add('separator-glow')
      const glowPath = glow.querySelector('path')
      line.append(svg, glow)
      curves.set(line, { svg, path, glow, glowPath, width: 0 })
      resizeObserver.observe(line)
    })
    window.addEventListener('themechange', syncSeparatorColors)
    media = matchMedia('(prefers-reduced-motion: reduce), (hover: none)')
    media.addEventListener('change', clear)
    root.value.addEventListener('pointermove', move, { passive: true })
    root.value.addEventListener('pointerleave', clear)
    window.addEventListener('scroll', clear, { passive: true })
    window.addEventListener('blur', clear)
    document.addEventListener('visibilitychange', clear)
  })
  onBeforeUnmount(() => {
    clear()
    window.removeEventListener('themechange', syncSeparatorColors)
    resizeObserver?.disconnect()
    curves.forEach(({ svg, glow }) => { svg.remove(); glow.remove() })
    curves.clear()
    media?.removeEventListener('change', clear)
    root.value?.removeEventListener('pointermove', move)
    root.value?.removeEventListener('pointerleave', clear)
    window.removeEventListener('scroll', clear)
    window.removeEventListener('blur', clear)
    document.removeEventListener('visibilitychange', clear)
  })
}
