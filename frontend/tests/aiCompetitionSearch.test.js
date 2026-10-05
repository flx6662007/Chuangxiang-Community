import test from 'node:test'
import assert from 'node:assert/strict'
import { createAssistantReader } from '../src/services/assistantClient.js'

const result = { mode: 'keyword', keywords: ['机器人'], count: 1, results: [
  { catalog: { code: '2026033', name: '机器人大赛' }, match_reason: '名称包含机器人' },
] }

test('助手向真实后端发送查询、取消信号并保留目录链接标识', async () => {
  const calls = []
  const reader = createAssistantReader({ get: async (...args) => { calls.push(args); return { data: result } } })
  const signal = new AbortController().signal
  assert.deepEqual(await reader.search(' 机器人 ', { signal }), result)
  assert.deepEqual(calls, [['/ai/search/', { params: { q: '机器人' }, signal }]])
})

test('有效空结果与服务错误分开处理，不回退到模拟赛事', async () => {
  const data = { mode: 'keyword', keywords: ['不存在'], count: 0, results: [] }
  assert.deepEqual(await createAssistantReader({ get: async () => ({ data }) }).search('不存在'), data)
  const error = Object.assign(new Error('offline'), { code: 'ERR_NETWORK' })
  await assert.rejects(createAssistantReader({ get: async () => { throw error } }).search('AI'), value => value === error)
})

test('输入超界或返回旧模拟契约时不展示结果', async () => {
  let calls = 0
  const reader = createAssistantReader({ get: async () => { calls++; return { data: { results: [{ competition: {} }] } } } })
  await assert.rejects(reader.search(' '), TypeError)
  await assert.rejects(reader.search('a'.repeat(501)), TypeError)
  assert.equal(calls, 0)
  await assert.rejects(reader.search('AI'), /Invalid assistant response/)
})

test('取消请求保留取消状态供页面忽略过期结果', async () => {
  const error = Object.assign(new Error('canceled'), { code: 'ERR_CANCELED' })
  await assert.rejects(createAssistantReader({ get: async () => { throw error } }).search('AI'), value => value.code === 'ERR_CANCELED')
})
