import http from './http'
import { ensureCsrf } from './accounts'

export async function requestAIChat(messages, { signal } = {}) {
  await ensureCsrf()
  const { data } = await http.post('/ai/chat/', { messages }, {
    signal,
    timeout: 130000,
  })
  const message = data?.message
  if (message?.role !== 'assistant' || typeof message.content !== 'string' || !message.content.trim()) {
    throw new Error('Invalid AI response')
  }
  return { role: 'assistant', content: message.content }
}
