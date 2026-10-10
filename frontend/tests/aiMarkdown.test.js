import test from 'node:test'
import assert from 'node:assert/strict'
import { renderAIMessage } from '../src/utils/aiMarkdown.js'

test('生成中和中断内容的链接不可点击，最终只放行来源链接', () => {
  const message = { content: '[资料](https://example.org/) [未知](https://other.org/) ![图片](https://evil.org/a.png)', sources: [{ url: 'https://example.org/' }] }
  for (const state of [{ generating: true }, { incomplete: true }]) assert.doesNotMatch(renderAIMessage({ ...message, ...state }), /<a |<img/)
  const html = renderAIMessage(message)
  assert.match(html, /href="https:\/\/example.org\/"/)
  assert.doesNotMatch(html, /href="https:\/\/other.org\/"|<img/)
  assert.match(html, /noopener noreferrer/)
})

test('未闭合 Markdown 及 HTML 不能插入可执行内容', () => {
  const html = renderAIMessage({ content: '<script>alert(1)</script> [链接](javascript:alert(1)) **尚未完成', generating: true })
  assert.doesNotMatch(html, /<script>|<a /)
})

test('完成回答允许已登记的项目和文档入口，仍阻止模型猜测的同域链接', () => {
  const homepage = 'https://www.zotero.org/'
  const docs = 'https://www.zotero.org/support/quick_start_guide'
  const message = { content: `[主页](${homepage}) [文档](${docs}) [猜测](https://www.zotero.org/unknown)`,
    sources: [{ kind: 'resource', url: 'https://github.com/zotero/zotero', links: [
      { label: '项目主页', url: homepage }, { label: '入门文档', url: docs },
    ] }] }
  const html = renderAIMessage(message)
  assert.match(html, /href="https:\/\/www.zotero.org\/"/)
  assert.match(html, /href="https:\/\/www.zotero.org\/support\/quick_start_guide"/)
  assert.doesNotMatch(html, /href="https:\/\/www.zotero.org\/unknown"/)
  assert.doesNotMatch(renderAIMessage({ ...message, generating: true }), /<a /)
  assert.doesNotMatch(renderAIMessage({ ...message, incomplete: true }), /<a /)
})
