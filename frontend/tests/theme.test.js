import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveTheme, revealGeometry } from '../src/utils/theme.js'

test('saved choice wins; absent or invalid values follow the system', () => {
  assert.equal(resolveTheme('light', true), 'light')
  assert.equal(resolveTheme('dark', false), 'dark')
  assert.equal(resolveTheme(null, true), 'dark')
  assert.equal(resolveTheme('invalid', false), 'light')
})

test('pointer origin covers every viewport corner, including edge clicks', () => {
  const rect = { left: 700, top: 20, width: 32, height: 32 }
  for (const [x, y] of [[0, 0], [1200, 800], [735, 31], [0, 400]]) {
    const result = revealGeometry({ detail: 1, clientX: x, clientY: y }, rect, 1200, 800)
    assert.equal(result.x, x)
    assert.equal(result.y, y)
    for (const [cx, cy] of [[0, 0], [1200, 0], [0, 800], [1200, 800]]) {
      assert.ok(result.radius >= Math.hypot(cx - x, cy - y))
    }
  }
})

test('keyboard and missing pointer coordinates use the button centre', () => {
  const rect = { left: 700, top: 20, width: 32, height: 32 }
  for (const event of [{ detail: 0, clientX: 0, clientY: 0 }, {}]) {
    const result = revealGeometry(event, rect, 1200, 800)
    assert.equal(result.x, 716)
    assert.equal(result.y, 36)
  }
})
