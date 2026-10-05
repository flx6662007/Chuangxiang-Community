import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getSessionProfile } from '../api/accounts'
import { SESSION_EVENT, SESSION_STORAGE_KEY } from '../utils/sessionEvents'

// 草稿仍由 API 校验权限；会话变化和切出页面时清掉内部预览，防止账号切换后残留。
export function useLibrarySession(clearPreview, reload) {
  const profile = ref(null)
  let version = 0
  let disposed = false
  const canPreview = computed(() => profile.value?.can_preview_library === true)

  async function refresh(reloadData = false) {
    const request = ++version
    profile.value = null
    try {
      const result = await getSessionProfile()
      if (request !== version || disposed) return
      profile.value = result
    } catch {
      // 公开资料不依赖登录成功；内部预览请求仍会由后端拒绝。
    }
    if (request === version && !disposed && reloadData) reload()
  }
  function clearSession() {
    version++
    profile.value = null
    clearPreview()
  }
  function changed() {
    clearSession()
    if (document.visibilityState === 'visible') refresh(true)
  }
  function storage(event) {
    if (event.key === SESSION_STORAGE_KEY || event.key === null) changed()
  }
  function visibility() {
    if (document.visibilityState === 'visible') refresh(true)
    else {
      clearSession()
    }
  }
  function pageShow() {
    if (document.visibilityState === 'visible') refresh(true)
  }
  onMounted(() => {
    window.addEventListener(SESSION_EVENT, changed)
    window.addEventListener('storage', storage)
    window.addEventListener('pagehide', clearSession)
    window.addEventListener('pageshow', pageShow)
    document.addEventListener('visibilitychange', visibility)
    refresh()
  })
  onBeforeUnmount(() => {
    disposed = true
    version++
    window.removeEventListener(SESSION_EVENT, changed)
    window.removeEventListener('storage', storage)
    window.removeEventListener('pagehide', clearSession)
    window.removeEventListener('pageshow', pageShow)
    document.removeEventListener('visibilitychange', visibility)
  })
  return { canPreview }
}
