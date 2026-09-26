import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getSessionProfile } from '../api/accounts'
import {
  createSessionFence,
  SESSION_EVENT,
  SESSION_STORAGE_KEY,
} from '../utils/sessionEvents'
import { governanceError } from '../utils/governance'

// 离开标签、退出或切换账号时立即清空私密记录，丢弃旧请求的迟到结果。
export function useGovernanceSession(clearData, loadData) {
  const profile = ref(null),
    checking = ref(true),
    sessionError = ref('')
  const fence = createSessionFence()
  let controller
  function clear() {
    fence.invalidate()
    controller?.abort()
    profile.value = null
    clearData()
  }
  async function refresh() {
    clear()
    const token = fence.capture()
    controller = new AbortController()
    checking.value = true
    sessionError.value = ''
    try {
      const user = await getSessionProfile()
      if (!fence.isCurrent(token)) return
      profile.value = user
      if (user)
        await loadData({
          token,
          signal: controller.signal,
          isCurrent: () => fence.isCurrent(token),
        })
    } catch (error) {
      if (fence.isCurrent(token) && error.code !== 'ERR_CANCELED') {
        clearData()
        profile.value = null
        sessionError.value = governanceError(error)
      }
    } finally {
      if (fence.isCurrent(token)) checking.value = false
    }
  }
  function changed() {
    clear()
    if (document.visibilityState === 'visible') refresh()
  }
  function storage(event) {
    if (event.key === SESSION_STORAGE_KEY || event.key === null) changed()
  }
  function visibility() {
    if (document.visibilityState === 'visible') refresh()
    else clear()
  }
  function pageShow() {
    if (document.visibilityState === 'visible') refresh()
  }
  onMounted(() => {
    window.addEventListener(SESSION_EVENT, changed)
    window.addEventListener('storage', storage)
    window.addEventListener('pagehide', clear)
    window.addEventListener('pageshow', pageShow)
    document.addEventListener('visibilitychange', visibility)
    refresh()
  })
  onBeforeUnmount(() => {
    clear()
    window.removeEventListener(SESSION_EVENT, changed)
    window.removeEventListener('storage', storage)
    window.removeEventListener('pagehide', clear)
    window.removeEventListener('pageshow', pageShow)
    document.removeEventListener('visibilitychange', visibility)
  })
  return {
    profile,
    checking,
    sessionError,
    refresh,
    capture: fence.capture,
    isCurrent: fence.isCurrent,
    signal: () => controller?.signal,
  }
}
