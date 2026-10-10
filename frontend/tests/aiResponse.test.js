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

test('资源来源保留已登记入口，过滤任意字段和不安全链接', () => {
  const homepage = { label: '项目主页', url: 'https://www.zotero.org/' }
  const result = parseAIReply({ message: { role: 'assistant', content: '资料入口' }, sources: [
    { id: 1, kind: 'resource', title: 'Zotero', url: 'https://github.com/zotero/zotero', links: [homepage, homepage,
      { label: '任意指令', url: 'https://malicious.edu.cn/' },
      { label: '入门文档', url: 'javascript:alert(1)' },
      { label: '官方文档', url: 'https://user:pass@www.zotero.org/' }] },
    { id: 2, kind: 'web', title: '网页', url: 'https://www.zotero.org/', links: [homepage] },
  ] })
  assert.deepEqual(result.sources[0].links, [homepage])
  assert.deepEqual(result.sources[1].links, [])
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

test('科研字段及多来源独立保留，过滤未知字段、危险链接和重复链接', () => {
  const url = 'https://lab.example.edu.cn/research'
  const link = { label: '研究介绍', url }
  const result = parseAIReply({ message: { role: 'assistant', content: '研究介绍[1]' },
    recommendations: [{ object_type: 'research_opportunity', title: '实验室', reason: '研究资料', source_url: url,
      facts: { summary: '电子皮肤', roles: '博士生', privateNotes: '不能公开' },
      field_links: { summary: [link, link, { label: '危险', url: 'javascript:alert(1)' }],
        roles: [{ label: '招募详情', url: 'https://lab.example.edu.cn/join' }] } }] })
  const card = result.recommendations[0]
  assert.deepEqual(card.facts, { summary: '电子皮肤', roles: '博士生' })
  assert.deepEqual(card.field_links.summary, [link])
  assert.equal(card.field_links.roles[0].url, 'https://lab.example.edu.cn/join')
})

test('站内记录编号和详情路由在聊天来源中保留', () => {
  const result = parseAIReply({ message: { role: 'assistant', content: '见来源[1]' },
    sources: [{ id: 1, kind: 'research_opportunity', entity_id: 'db-19', database_id: '19',
      title: '实验室', url: 'https://lab.example.edu.cn', internal_url: '/research/19' },
    { id: 2, kind: 'team', entity_id: 'db-8', title: '组队招募', url: '/teams/8', internal_url: '/teams/8' }],
    recommendations: [{ object_type: 'team', object_id: 'db-8', database_id: '8', title: '组队招募',
      reason: '公开卡片', source_url: '/teams/8', internal_url: '/teams/8' }] })
  assert.equal(result.sources[0].internal_url, '/research/19')
  assert.equal(result.sources[0].database_id, '19')
  assert.equal(result.sources[1].internal_url, '/teams/8')
  assert.equal(result.recommendations[0].object_id, 'db-8')
  assert.equal(result.recommendations[0].internal_url, '/teams/8')
})

test('组队来源和推荐仅允许与公开记录编号一致的站内地址', () => {
  const invalid = ['/teams/9', '/teams/8?admin=true', '//evil.org/teams/8', '/admin/8', '/teams/08', 'javascript:alert(1)']
  const result = parseAIReply({ message: { role: 'assistant', content: '组队资料' },
    sources: invalid.map((url, index) => ({ id: index + 1, kind: 'team', entity_id: 'db-8', title: '招募', url, internal_url: url })),
    recommendations: invalid.map(url => ({ object_type: 'team', object_id: 'db-8', title: '招募', reason: '公开招募', source_url: url, internal_url: url })),
  })
  assert.deepEqual(result.sources, [])
  assert.deepEqual(result.recommendations, [])
})

test('资源卡片与来源保留同一个站内详情入口，拒绝错配编号', () => {
  const base = { title: 'Zotero', source_url: 'https://github.com/zotero/zotero', reason: '文献管理' }
  const result = parseAIReply({ message: { role: 'assistant', content: '资料入口' },
    sources: [{ kind: 'resource', entity_id: 'zotero', title: 'Zotero', url: base.source_url, internal_url: '/resources/zotero' }],
    recommendations: [{ ...base, object_type: 'resource', object_id: 'zotero', internal_url: '/resources/zotero' },
      { ...base, object_type: 'resource', object_id: 'zotero', internal_url: '/resources/other' }],
  })
  assert.equal(result.recommendations[0].internal_url, result.sources[0].internal_url)
  assert.equal(result.recommendations[1].internal_url, null)
})
