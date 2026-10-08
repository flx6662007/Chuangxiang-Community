import { ref } from 'vue'

// 完整记录留在当前组件内存；每次仅发送最近 20 轮、最多 60000 字符。
export function recentChatMessages(messages) {
  const history = messages.map(({ role, content }) => ({ role, content }))
  let size = history.reduce((total, message) => total + message.content.length, 0)
  while (history.length > 1 && (history.length > 41 || size > 60000)) {
    size -= history[0].content.length + history[1].content.length
    history.splice(0, 2)
  }
  return history
}

export function chatErrorMessage(error) {
  if (['ECONNABORTED', 'ETIMEDOUT'].includes(error.code)) return 'AI 回复超时，请稍后重试。'
  const code = error.response?.data?.code
  const messages = {
    ai_configuration_error: 'AI 服务尚未配置完成，请联系管理员。',
    ai_authentication_error: 'AI 服务认证失败，请联系管理员检查配置。',
    ai_insufficient_balance: 'AI 服务余额不足，请联系管理员。',
    ai_input_error: '消息格式或长度不符合要求，请缩短内容后重试。',
    ai_timeout: 'AI 回复超时，请稍后重试。',
    ai_connection_error: '暂时无法连接 AI 服务，请稍后重试。',
    ai_rate_limit: '发送太频繁，请稍后重试。',
    ai_upstream_error: 'AI 服务暂时异常，请稍后重试。',
    ai_response_error: 'AI 未返回完整有效的回答，请缩短问题后重试。',
    csrf_failed: '页面凭据失效，请刷新页面后重试。',
  }
  return messages[code] || (error.response ? 'AI 服务暂时不可用，请稍后重试。' : '连接失败，请确认网络和后端服务已启动。')
}

export function useAIChat(request) {
  const messages = ref([])
  const pending = ref(false)
  const error = ref('')
  const failed = ref(false)
  const phase = ref('idle')
  let active
  let disposed = false

  function flushDelta(run) {
    clearTimeout(run.timer)
    run.timer = undefined
    if (active === run && run.queued && messages.value[run.index]) messages.value[run.index].content += run.queued
    run.queued = ''
  }

  function interrupt(run, message) {
    if (active !== run) return
    flushDelta(run)
    const answer = messages.value[run.index]
    if (answer?.content) Object.assign(answer, { generating: false, incomplete: true })
    else messages.value.splice(run.index, 1)
    active = undefined
    pending.value = false
    phase.value = 'idle'
    error.value = message
    failed.value = true
    run.controller.abort()
  }

  async function submit(text, { retry = false, mode = 'smart', webSearch = false } = {}) {
    if (pending.value || disposed) return false
    const content = typeof text === 'string' ? text.trim() : ''
    if (!retry && (!content || content.length > 2000)) return false
    if (retry && !failed.value) return false
    if (failed.value && messages.value.at(-1)?.incomplete) messages.value.pop()
    if (!retry) {
      // 失败的问题仍显示到用户重试或改问为止；错误不进入模型上下文。
      if (failed.value) messages.value.pop()
      messages.value.push({ role: 'user', content })
    }
    const history = recentChatMessages(messages.value)
    const conversationContext = messages.value.filter(message => message.role === 'assistant' && !message.incomplete).at(-1)?.conversation_context
    const assistantIndex = messages.value.length
    messages.value.push({ role: 'assistant', content: '', generating: true })
    pending.value = true
    failed.value = false
    error.value = ''
    phase.value = 'retrieving'
    const run = { controller: new AbortController(), index: assistantIndex, queued: '', timer: undefined }
    active = run
    try {
      const reply = await request(history, { signal: run.controller.signal, mode, conversationContext, webSearch,
        onStatus(value) {
          if (active === run && !disposed && ['retrieving', 'generating'].includes(value)) phase.value = value
        }, onDelta(chunk) {
        if (disposed || active !== run || typeof chunk !== 'string' || !chunk) return
        phase.value = 'generating'
        run.queued += chunk
        if (!messages.value[assistantIndex].content) flushDelta(run)
        else if (!run.timer) run.timer = setTimeout(() => flushDelta(run), 32)
      } })
      if (disposed || active !== run) return false
      flushDelta(run)
      Object.assign(messages.value[assistantIndex], reply, { generating: false })
      return true
    } catch (cause) {
      if (!disposed && active === run) interrupt(run, cause.name === 'AbortError' ? '已停止生成。' : chatErrorMessage(cause))
      return false
    } finally {
      clearTimeout(run.timer)
      if (active === run) {
        active = undefined
        pending.value = false
        phase.value = 'idle'
      }
    }
  }

  function stop() {
    if (!pending.value) return false
    interrupt(active, '已停止生成。')
    return true
  }

  function dispose() {
    disposed = true
    if (active) {
      clearTimeout(active.timer)
      active.controller.abort()
      active = undefined
    }
    pending.value = false
    phase.value = 'idle'
    if (messages.value.at(-1)?.generating) messages.value.pop()
  }

  function clear() {
    if (pending.value) return false
    messages.value = []
    error.value = ''
    failed.value = false
    return true
  }

  return { messages, pending, phase, error, failed, submit, stop, dispose, clear }
}
