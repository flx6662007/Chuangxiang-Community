import assert from 'node:assert/strict'
import test from 'node:test'
import { mockResources } from '../src/mocks/resources.js'
import {
  getResource,
  listResources,
  resourceCategories,
  resourceDirections,
} from '../src/services/resources.js'

test('resource examples cover every category and direction with unique IDs', () => {
  assert.equal(mockResources.length, 15)
  assert.equal(new Set(mockResources.map((item) => item.id)).size, mockResources.length)
  for (const category of resourceCategories) {
    assert.ok(mockResources.some((item) => item.category === category.value))
  }
  for (const direction of resourceDirections.filter((item) => item.value)) {
    assert.ok(mockResources.some((item) => item.direction === direction.value))
  }
})

test('search, direction and category narrow the same resource list', async () => {
  const { results } = await listResources({ search: '论文 原文', direction: 'research', category: 'source' })
  assert.deepEqual(results.map((item) => item.id), ['arxiv-source'])
  const none = await listResources({ search: '论文', direction: 'competition', category: 'source' })
  assert.equal(none.count, 0)
})

test('resource detail lookup returns the same item or null', async () => {
  const item = await getResource('zotero-references')
  assert.equal(item?.title, 'Zotero：整理文献与引用')
  assert.equal(await getResource('missing-resource'), null)
})
