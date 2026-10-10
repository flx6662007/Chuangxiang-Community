import { nextTick, readonly, ref } from 'vue'
import { isTheme, resolveTheme, revealGeometry, THEME_STORAGE_KEY } from '../utils/theme'

const theme = ref('dark')
const changing = ref(false)
let initialized = false
let preference = null
let system
let fallbackTimer

function applyTheme(value, persist = false) {
  theme.value = value
  document.documentElement.dataset.theme = value
  const favicon = document.getElementById('site-favicon')
  if (favicon) favicon.href = `${import.meta.env.BASE_URL}favicon-${value}.svg`
  if (persist) {
    preference = value
    try { localStorage.setItem(THEME_STORAGE_KEY, value) } catch { /* Private storage may be unavailable. */ }
  }
  window.dispatchEvent(new CustomEvent('themechange', { detail: value }))
}

export function initializeTheme() {
  if (initialized) return
  initialized = true
  system = window.matchMedia('(prefers-color-scheme: dark)')
  try { preference = localStorage.getItem(THEME_STORAGE_KEY) } catch { /* Use the system preference. */ }
  applyTheme(resolveTheme(preference, system.matches))
  system.addEventListener('change', () => {
    if (!isTheme(preference)) applyTheme(resolveTheme(null, system.matches))
  })
  window.addEventListener('storage', event => {
    if (event.key !== THEME_STORAGE_KEY && event.key !== null) return
    preference = event.newValue
    applyTheme(resolveTheme(preference, system.matches))
  })
}

async function toggleTheme(event) {
  if (changing.value) return
  const next = theme.value === 'dark' ? 'light' : 'dark'
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduced) {
    applyTheme(next, true)
    return
  }
  if (typeof document.startViewTransition !== 'function') {
    const root = document.documentElement
    clearTimeout(fallbackTimer)
    root.classList.add('theme-fallback')
    // Establish the old colours before applying the fallback transition.
    getComputedStyle(root).backgroundColor
    applyTheme(next, true)
    fallbackTimer = setTimeout(() => root.classList.remove('theme-fallback'), 180)
    return
  }

  const root = document.documentElement
  const rect = event.currentTarget.getBoundingClientRect()
  const { x, y, radius } = revealGeometry(event, rect, window.innerWidth, window.innerHeight)
  changing.value = true
  root.style.setProperty('--theme-origin-x', `${x}px`)
  root.style.setProperty('--theme-origin-y', `${y}px`)
  root.dataset.themeTransition = ''
  let transition
  try {
    transition = document.startViewTransition(async () => {
      root.classList.add('theme-capture')
      applyTheme(next, true)
      await nextTick()
    })
    // Observe all promises, including a skipped/hidden-document transition.
    const settled = transition.finished.catch(() => {})
    transition.updateCallbackDone.catch(() => {})
    await transition.ready
    root.classList.remove('theme-capture')
    const animation = root.animate({
      clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`],
    }, {
      duration: 600,
      easing: 'cubic-bezier(.22, 1, .36, 1)',
      fill: 'both',
      pseudoElement: '::view-transition-new(root)',
    })
    await animation.finished
    await settled
  } catch {
    transition?.skipTransition()
    applyTheme(next, true)
  } finally {
    root.classList.remove('theme-capture')
    delete root.dataset.themeTransition
    root.style.removeProperty('--theme-origin-x')
    root.style.removeProperty('--theme-origin-y')
    changing.value = false
  }
}

export function useTheme() {
  return { theme: readonly(theme), changing: readonly(changing), toggleTheme }
}
