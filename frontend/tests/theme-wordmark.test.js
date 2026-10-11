import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compileStyle, parse } from '@vue/compiler-sfc'

test('compiled dark wordmark filter targets only the logo image, never the page root', () => {
  const filename = new URL('../src/components/XiaochuangLogo.vue', import.meta.url)
  const { descriptor } = parse(readFileSync(filename, 'utf8'))
  const { code, errors } = compileStyle({ source: descriptor.styles[0].content, filename: filename.pathname, id: 'data-v-test', scoped: true })
  assert.deepEqual(errors, [])
  const rules = [...code.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(([, selector]) => selector.includes('data-theme'))
  assert.ok(rules.length)
  for (const [, selector] of rules) assert.match(selector, /\.xiaochuang-logo[^{}]*\simg\s*$/)
})
