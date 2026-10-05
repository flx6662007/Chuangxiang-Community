import test from 'node:test'
import assert from 'node:assert/strict'
import { libraryPage, libraryText, libraryQuery, paginatedLibrary, publicResourceQuery } from '../src/utils/library.js'

test('资料分页不接受非法页码，筛选文本限制长度', () => {
  for (const value of [undefined, 0, -1, 1.5, 'x', Infinity]) assert.equal(libraryPage(value), 1)
  assert.equal(libraryPage('3'), 3)
  assert.equal(libraryText(['private']), '')
  assert.equal(libraryText('x'.repeat(400)).length, 200)
})

test('查询保留明确的目录筛选与内部预览标志，不隐式加草稿权限', () => {
  assert.deepEqual(libraryQuery({ search: '机器人', catalog_code: '2026025', preview: undefined, page: 2 }), {
    search: '机器人', catalog_code: '2026025', page: 2,
  })
  assert.deepEqual(libraryQuery({ preview: 1, category: '', page: 1 }), { preview: 1, page: 1 })
})

test('资料接口异常数据不能被当成正常空列表或示例数据', () => {
  assert.throws(() => paginatedLibrary({ count: 255 }), /Invalid/)
  assert.throws(() => paginatedLibrary({ results: [], count: -1 }), /Invalid/)
  const empty = { results: [], count: 0 }
  assert.equal(paginatedLibrary(empty), empty)
})

test('资源旧链接去除 preview，保留搜索、目录、分类和页码', () => {
  const query = { search: '机器人', catalog_code: '2026033', category: 'course', page: '2', preview: '1' }
  assert.deepEqual(publicResourceQuery(query), { search: '机器人', catalog_code: '2026033', category: 'course', page: '2' })
  assert.equal(query.preview, '1')
})
