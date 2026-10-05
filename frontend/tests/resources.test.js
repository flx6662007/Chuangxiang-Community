import assert from 'node:assert/strict'
import test from 'node:test'
import { createResourceReader } from '../src/services/resourceClient.js'

test('真实资源请求将搜索、目录、分页和取消信号传给 API，不默认预览草稿', async () => {
  const calls = []
  const reader = createResourceReader({ get: async (...args) => {
    calls.push(args)
    return { data: { results: [], count: 0 } }
  } })
  const params = { search: '机器人', catalog_code: '2026025', page: 3, page_size: 20 }
  const signal = new AbortController().signal
  assert.deepEqual(await reader.listResources(params, signal), { results: [], count: 0 })
  assert.deepEqual(calls, [['/resources/', { params, signal }]])
  assert.equal(calls[0][1].params.preview, undefined)
})

test('资源列表、详情和分类始终公开读取，不继承旧链接的 preview 参数', async () => {
  const calls = []
  const reader = createResourceReader({ get: async (...args) => {
    calls.push(args)
    return { data: { results: [], count: 0, categories: [], directions: [] } }
  } })
  const params = { preview: '1' }
  await reader.listResources(params)
  await reader.getResource('resource:2026025/rules', params)
  await reader.listResourceTaxonomies(params)
  assert.deepEqual(calls.map(call => call[0]), ['/resources/', '/resources/resource%3A2026025%2Frules/', '/resources/options/'])
  for (const call of calls) assert.deepEqual(call[1].params, {})
  assert.deepEqual(params, { preview: '1' })
})

test('权限拒绝、404和网络错误保持失败，不返回假数据或伪空列表', async () => {
  for (const status of [403, 404, 500]) {
    const error = Object.assign(new Error('request failed'), { response: { status } })
    const reader = createResourceReader({ get: async () => { throw error } })
    await assert.rejects(reader.listResources(), value => value === error)
    await assert.rejects(reader.getResource('missing'), value => value === error)
  }
})

test('资源接口错误契约与正常空库分开处理', async () => {
  const reader = createResourceReader({ get: async () => ({ data: { count: 10, results: null } }) })
  await assert.rejects(reader.listResources(), /Invalid library response/)
  await assert.rejects(reader.listResourceTaxonomies(), /Invalid resource taxonomy response/)
})
