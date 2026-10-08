import http from './http'
import { ensureCsrf } from './csrf'
import { parseAIReply } from './aiResponse.js'

export async function getAIStatus(signal) {
  return (await http.get('/ai/status/', { signal })).data
}

export async function requestAIChat(messages, { signal, mode = 'smart', conversationContext, webSearch = false } = {}) {
  await ensureCsrf()
  const { data } = await http.post('/ai/chat/', { messages, mode, web_search: webSearch, ...(conversationContext ? { conversation_context: conversationContext } : {}) }, {
    signal,
    timeout: 130000,
  })
  return parseAIReply(data)
}
