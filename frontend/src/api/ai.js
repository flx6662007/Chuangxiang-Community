import http from './http'
import { ensureCsrf } from './accounts'
import { parseAIReply } from './aiResponse.js'

export async function getAIStatus(signal) {
  return (await http.get('/ai/status/', { signal })).data
}

export async function requestAIChat(messages, { signal, mode = 'smart' } = {}) {
  await ensureCsrf()
  const { data } = await http.post('/ai/chat/', { messages, mode }, {
    signal,
    timeout: 130000,
  })
  return parseAIReply(data)
}
