import test from 'node:test'
import assert from 'node:assert/strict'
import { mockAICompetitionSearch } from '../src/mocks/aiCompetitionSearch.js'
import { searchCompetitionsByAI } from '../src/services/aiCompetitionSearch.js'

test('示例自然语言返回固定契约和可供现有卡片展示的本地赛事', () => {
  const data = mockAICompetitionSearch('我是大二物理专业学生，想找人工智能相关、近期还能报名、最好可以组队参加的比赛。')
  assert.deepEqual(data.interpretation, {
    major: '物理',
    grade: '大二',
    interests: ['人工智能'],
    participationType: 'team',
    registrationStatus: 'open',
  })
  assert.ok(data.results.length > 0)
  for (const { competition, matchReason } of data.results) {
    assert.equal(typeof competition.id, 'number')
    assert.match(competition.title, /【演示】/)
    assert.ok(competition.category?.name)
    assert.ok(Array.isArray(competition.tags))
    assert.equal(competition.deadline_kind, 'registration')
    assert.equal(competition.deadline_status, 'open')
    assert.ok(['team', 'both'].includes(competition.participation_type))
    assert.match(matchReason, /人工智能/)
  }
})

test('快捷输入可匹配，未识别方向返回空结果', () => {
  assert.ok(mockAICompetitionSearch('适合大二学生').results.length > 0)
  assert.ok(mockAICompetitionSearch('科研创新类').results.length > 0)
  assert.deepEqual(mockAICompetitionSearch('天文考古比赛').results, [])
})

test('已取消的搜索立即结束，模拟错误可稳定复现', async () => {
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(searchCompetitionsByAI('AI 相关', { signal: controller.signal }), { name: 'AbortError' })
  await assert.rejects(searchCompetitionsByAI('模拟错误'), /模拟 AI 搜索暂时不可用/)
})

test('进行中的旧搜索可取消，新搜索仍正常返回', async () => {
  const controller = new AbortController()
  const previous = searchCompetitionsByAI('AI 相关', { signal: controller.signal })
  controller.abort()
  const current = searchCompetitionsByAI('近期可报名')
  await assert.rejects(previous, { name: 'AbortError' })
  assert.ok((await current).results.length > 0)
})
