import http from './http'
import { ensureCsrf } from './accounts'
import { parseAIReply } from './aiResponse.js'

export async function requestAIChat(messages, { signal } = {}) {
  await ensureCsrf()
  const { data } = await http.post('/ai/chat/', { messages }, {
    signal,
    timeout: 130000,
  })
  return parseAIReply(data)
}
