export function csrfFromCookie(cookie) {
  const entry = cookie.split(';').map((part) => part.trim()).find((part) => part.startsWith('csrftoken='))
  if (!entry) return ''
  try { return decodeURIComponent(entry.slice('csrftoken='.length)) } catch { return '' }
}

export function isPendingPasswordReset(body) {
  return body?.status === 401 && body?.meta?.is_authenticated === false &&
    body?.data?.flows?.some((flow) => flow.id === 'password_reset_by_code' && flow.is_pending === true) === true
}

export function isSignedOut(body) {
  return body?.status === 401 && body?.meta?.is_authenticated === false &&
    Array.isArray(body?.data?.flows) && body.data.flows.some((flow) => flow.id === 'login')
}

export function isFinishedPasswordReset(body) {
  return isSignedOut(body) && !body.data.flows.some((flow) => flow.id === 'password_reset_by_code' && flow.is_pending)
}

const fieldNames = { email: '邮箱', password: '密码', wechat_id: '微信号', phone_number: '手机号', key: '验证码' }

// DRF SessionAuthentication 对匿名资料请求返回 403；不能与发信配额的 403 混淆。
export async function withProfileSessionCheck(operation, readSession) {
  try {
    return await operation()
  } catch (error) {
    error.accountContext = 'profile'
    if ([401, 403].includes(error.response?.status)) {
      try {
        const session = await readSession()
        error.sessionExpired = session.status === 401 && isSignedOut(session.data)
      } catch {
        // 无法检查会话时保留原错误，不能仅凭网络问题断言用户已退出。
      }
    }
    throw error
  }
}

export function accountErrorMessages(error, context = '') {
  const status = error.response?.status
  const body = error.response?.data
  if (error.sessionExpired) return ['登录状态已失效，请重新登录。']
  if (!status) return ['网络连接失败，请检查网络后重试。']
  if (status === 429) return ['操作过于频繁，请稍后再试。']
  if (status === 503) return ['邮件暂时无法发送，请稍后重试。']
  if (status >= 500) return ['服务暂时不可用，请稍后重试。']
  if (status === 403 && (body?.code === 'csrf_failed' ||
      (typeof body?.detail === 'string' && body.detail.startsWith('CSRF Failed:')))) return ['页面凭据失效，请刷新页面后重试。']
  if (status === 403 && context === 'send') return ['验证码暂时无法重发，可能发送过于频繁或已超过本次重发次数，请稍后重试。']
  if (status === 403 && error.accountContext === 'profile') return ['暂时无法读取或修改账号资料，请刷新账号状态后重试。']
  if (status === 403) return ['当前无法执行此操作，请刷新账号状态后重试。']
  if (status === 409) return ['当前验证流程已结束或过期，请重新发送验证码；如已登录，请刷新账号状态。']
  if (status === 401) return ['登录状态已失效，请重新登录。']
  if (Array.isArray(body?.errors)) {
    return body.errors.map((entry) => `${fieldNames[entry.param] ? fieldNames[entry.param] + '：' : ''}${entry.message || '请检查填写内容。'}`)
  }
  if (status === 400 && body && typeof body === 'object') {
    const messages = Object.entries(body).flatMap(([field, values]) => {
      const texts = Array.isArray(values) ? values : [values]
      return texts.filter((value) => typeof value === 'string').map((value) => `${fieldNames[field] ? fieldNames[field] + '：' : ''}${value}`)
    })
    if (messages.length) return messages
  }
  return ['请求未完成，请检查填写内容后重试。']
}
