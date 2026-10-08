import { parseAIReply } from './aiResponse.js'
import { csrfFromCookie } from '../utils/account.js'

function streamError(code) {
  const error = new Error('AI stream failed')
  error.response = { data: { code } }
  return error
}

export async function readAIStream(response, onDelta, onStatus = () => {}) {
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw streamError('ai_response_error')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = '', event = '', data = [], result
  let size = 0
  function dispatch() {
    if (!data.length) { event = ''; return }
    let payload
    try { payload = JSON.parse(data.join('\n')) } catch { throw streamError('ai_response_error') }
    if (event === 'delta') {
      if (typeof payload?.content !== 'string') throw streamError('ai_response_error')
      onDelta(payload.content)
    } else if (event === 'done') {
      result = parseAIReply(payload)
    } else if (event === 'status') {
      if (['retrieving', 'generating'].includes(payload?.phase)) onStatus(payload.phase)
    } else if (event === 'error') {
      throw streamError(typeof payload?.code === 'string' ? payload.code : 'ai_response_error')
    }
    event = ''
    data = []
  }
  try {
    while (result === undefined) {
      const { value, done } = await reader.read()
      if (done) break
      size += value.byteLength
      if (size > 1024 * 1024) throw streamError('ai_response_error')
      buffer += decoder.decode(value, { stream: true })
      let newline
      while ((newline = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newline).replace(/\r$/, '')
        buffer = buffer.slice(newline + 1)
        if (!line) dispatch()
        else if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
        if (result !== undefined) break
      }
    }
    if (result === undefined) throw streamError('ai_response_error')
    return result
  } finally {
    try { await reader.cancel() } catch { /* transport already closed */ }
    reader.releaseLock()
  }
}

export async function requestAIChatStream(messages, { signal, mode = 'smart', onDelta = () => {}, onStatus = () => {}, conversationContext, webSearch = false } = {}) {
  const { ensureCsrf } = await import('./csrf')
  await ensureCsrf()
  signal?.throwIfAborted()
  const controller = new AbortController()
  let timedOut = false
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timeout = setTimeout(() => { timedOut = true; controller.abort() }, 130000)
  try {
    const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
    const response = await fetch(`${base}/ai/chat/stream/`, {
      method: 'POST', credentials: 'include', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfFromCookie(document.cookie) },
      body: JSON.stringify({ messages, mode, web_search: webSearch, ...(conversationContext ? { conversation_context: conversationContext } : {}) }),
    })
    if (!response.ok) {
      let data
      try { data = await response.json() } catch { data = {} }
      throw streamError(typeof data?.code === 'string' ? data.code : 'ai_unavailable')
    }
    return await readAIStream(response, onDelta, onStatus)
  } catch (error) {
    if (timedOut) throw streamError('ai_timeout')
    throw error
  } finally {
    clearTimeout(timeout)
    signal?.removeEventListener('abort', abort)
  }
}
