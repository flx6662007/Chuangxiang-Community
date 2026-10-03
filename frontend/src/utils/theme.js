export const THEME_STORAGE_KEY = 'chuangxiang-theme'
export const isTheme = value => value === 'dark' || value === 'light'

export function resolveTheme(saved, systemDark) {
  return isTheme(saved) ? saved : systemDark ? 'dark' : 'light'
}

export function revealGeometry(event, rect, width, height) {
  const hasPointer = event?.detail !== 0 && Number.isFinite(event?.clientX) && Number.isFinite(event?.clientY)
  const x = Math.max(0, Math.min(width, hasPointer ? event.clientX : rect.left + rect.width / 2))
  const y = Math.max(0, Math.min(height, hasPointer ? event.clientY : rect.top + rect.height / 2))
  return { x, y, radius: Math.hypot(Math.max(x, width - x), Math.max(y, height - y)) }
}
