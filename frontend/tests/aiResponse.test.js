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

test('结构化推荐只接受安全来源，保留关联资源和审核标记', () => {
  const answer = parseAIReply({
    message: { role: 'assistant', content: '推荐资料[1]' },
    recommendations: [
      { object_type: 'research_opportunity', title: '机器人导航课题', reason: '方向匹配',
        source_url: 'https://www.tongji.edu.cn/research', reviewed: true,
        research_group_label: '导航组', related_resources: [
          { title: '入门课程', source_url: 'https://www.tongji.edu.cn/course' },
          { title: '恶意资料', source_url: 'javascript:alert(1)' },
        ] },
      { object_type: 'resource', title: '危险链接', reason: '无', source_url: 'https://user:pass@bad.com/' },
    ],
  })
  assert.equal(answer.recommendations.length, 1)
  assert.equal(answer.recommendations[0].research_group_label, '导航组')
  assert.deepEqual(answer.recommendations[0].related_resources,
    [{ title: '入门课程', source_url: 'https://www.tongji.edu.cn/course' }])
})
