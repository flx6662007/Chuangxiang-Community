import test from 'node:test'
import assert from 'node:assert/strict'

import { parseAIReply } from '../src/api/aiResponse.js'
import { recentChatMessages } from '../src/composables/useAIChat.js'

test('response sources remain visible but never enter the next model request', () => {
  const answer = parseAIReply({
    message: { role: 'assistant', content: '见来源[1]' },
    retrieval: { knowledge: 'no_approved_knowledge' },
    sources: [
      { id: 1, title: '官网通知', url: 'https://www.tongji.edu.cn/notice', internal_url: '/competitions/12' },
      { id: 2, title: '恶意', url: 'javascript:alert(1)' },
      { id: 3, title: '错误内部路由', url: 'https://www.tongji.edu.cn/notice', internal_url: '/resources/mock-1' },
    ],
  })
  assert.equal(answer.sources.length, 2)
  assert.equal(answer.sources[1].internal_url, null)
  assert.deepEqual(recentChatMessages([{ role: 'user', content: '问题' }, answer]),
    [{ role: 'user', content: '问题' }, { role: 'assistant', content: '见来源[1]' }])
})
