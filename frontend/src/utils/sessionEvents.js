export const SESSION_EVENT = 'chuangxiang-session-changed'
export const SESSION_STORAGE_KEY = 'chuangxiang-session-change'

// 只广播会话变化，不存账号、令牌或表单内容。
export function announceSessionChange() {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event(SESSION_EVENT))
  try {
    window.localStorage.setItem(
      SESSION_STORAGE_KEY,
      String(Date.now()) + ':' + Math.random(),
    )
  } catch {
    // 禁用存储时，回到标签页仍会重新向服务器检查会话。
  }
}

export function createSessionFence() {
  let generation = 0
  return {
    capture: () => generation,
    invalidate: () => ++generation,
    isCurrent: (token) => token === generation,
  }
}
