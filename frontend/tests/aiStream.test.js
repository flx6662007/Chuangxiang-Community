import test from 'node:test'
import assert from 'node:assert/strict'
import { readAIStream } from '../src/api/aiStream.js'

function response(chunks) {
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk)
      controller.close()
    },
  })
  return new Response(stream, { headers: { 'content-type': 'text/event-stream; charset=utf-8' } })
}

test('SSE 按真实网络分片追加，完成事件保留结构化来源', async () => {
  const source = 'event: delta\ndata: {"content":"根据"}\n\nevent: delta\ndata: {"content":"你的需求"}\n\n'
    + 'event: done\ndata: {"message":{"role":"assistant","content":"根据你的需求"},"sources":[{"id":1,"title":"官网","url":"https://example.org"}],"recommendations":[]}\n\n'
  const bytes = new TextEncoder().encode(source)
  const deltas = []
  const result = await readAIStream(response([bytes.slice(0, 25), bytes.slice(25, 37), bytes.slice(37)]),
    chunk => deltas.push(chunk))
  assert.deepEqual(deltas, ['根据', '你的需求'])
  assert.equal(result.content, '根据你的需求')
  assert.equal(result.sources[0].url, 'https://example.org')
})

test('中途断开和错误事件都拒绝完成，不能永久生成', async () => {
  const encode = value => new TextEncoder().encode(value)
  await assert.rejects(readAIStream(response([encode('event: delta\ndata: {"content":"部分"}\n\n')]), () => {}))
  await assert.rejects(readAIStream(response([encode('event: error\ndata: {"code":"ai_timeout"}\n\n')]), () => {}),
    error => error.response.data.code === 'ai_timeout')
})
