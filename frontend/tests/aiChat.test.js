import test from 'node:test'
import assert from 'node:assert/strict'
import { useAIChat, recentChatMessages, chatErrorMessage } from '../src/composables/useAIChat.js'

const reply = { role: 'assistant', content: '我是创享 AI。' }

test('三轮对话携带之前的用户问题和模型回复', async () => {
  const calls = []
  const chat = useAIChat(async (messages) => { calls.push(messages); return reply })
  for (const question of ['你好，你是谁？', '你主要能帮我做什么？', '我刚才第一个问题问了什么？']) {
    assert.equal(await chat.submit(question), true)
  }
  assert.deepEqual(calls.map((messages) => messages.length), [1, 3, 5])
  assert.equal(calls[2][0].content, '你好，你是谁？')
  assert.equal(chat.messages.value.length, 6)
})

test('空消息、超长消息和进行中的重复提交不会发请求', async () => {
  let resolve
  let count = 0
  const chat = useAIChat(() => { count++; return new Promise((done) => { resolve = done }) })
  assert.equal(await chat.submit('  '), false)
  assert.equal(await chat.submit('字'.repeat(2001)), false)
  const first = chat.submit('你好')
  assert.equal(chat.pending.value, true)
  assert.equal(await chat.submit('重复'), false)
  resolve(reply)
  await first
  assert.equal(chat.pending.value, false)
  assert.equal(count, 1)
})

test('失败保留问题，重试不重复追加，不把错误带入上下文', async () => {
  const calls = []
  const chat = useAIChat(async (messages) => {
    calls.push(messages)
    if (calls.length === 1) throw { response: { data: { code: 'ai_insufficient_balance', detail: 'private' } } }
    return reply
  })
  assert.equal(await chat.submit('你好'), false)
  assert.match(chat.error.value, /余额不足/)
  assert.equal(chat.messages.value.length, 1)
  assert.equal(await chat.submit('', { retry: true }), true)
  assert.deepEqual(calls[0], calls[1])
  assert.equal(chat.messages.value.length, 2)
  assert.equal(chat.error.value, '')
})

test('失败后改问只替换失败的问题，已成功的历史仍保留', async () => {
  const calls = []
  const chat = useAIChat(async (messages) => {
    calls.push(messages)
    if (calls.length === 2) throw new Error('network')
    return reply
  })
  await chat.submit('第一问')
  await chat.submit('失败问题')
  await chat.submit('换一个问题')
  assert.deepEqual(calls[2].map((m) => m.content), ['第一问', reply.content, '换一个问题'])
})

test('卸载取消在途请求，迟到的结果不再更新会话', async () => {
  let resolve, signal
  const chat = useAIChat((_messages, options) => {
    signal = options.signal
    return new Promise((done) => { resolve = done })
  })
  const task = chat.submit('你好')
  chat.dispose()
  assert.equal(signal.aborted, true)
  resolve(reply)
  await task
  assert.equal(chat.messages.value.length, 1)
  assert.equal(await chat.submit('卸载后'), false)
})

test('上下文窗口按完整轮次截取，不改原记录、不发送界面字段', () => {
  const history = Array.from({ length: 30 }, (_, i) => [
    { role: 'user', content: `问题${i}`, local: true },
    { role: 'assistant', content: '答'.repeat(4000) },
  ]).flat()
  history.push({ role: 'user', content: '最新问题' })
  const selected = recentChatMessages(history)
  assert.ok(selected.length <= 41)
  assert.ok(selected.reduce((n, m) => n + m.content.length, 0) <= 60000)
  assert.equal(selected[0].role, 'user')
  assert.equal(selected.at(-1).content, '最新问题')
  assert.equal(history.length, 61)
  assert.ok(selected.every((m) => Object.keys(m).length === 2))
})

test('前端错误不展示原始服务器消息或异常详情', () => {
  const secret = 'private-server-error'
  assert.ok(!chatErrorMessage({ response: { data: { detail: secret } } }).includes(secret))
  assert.ok(!chatErrorMessage(new Error(secret)).includes(secret))
  assert.match(chatErrorMessage({ code: 'ECONNABORTED' }), /超时/)
})

test('四种模式复用同一会话调用，切换模式清空旧上下文', async () => {
  const calls = []
  const chat = useAIChat(async (messages, options) => { calls.push({ messages, mode: options.mode }); return reply })
  for (const mode of ['smart', 'competition', 'research', 'resource']) {
    assert.equal(chat.clear(), true)
    assert.equal(await chat.submit('查询资料', { mode }), true)
  }
  assert.deepEqual(calls.map(call => call.mode), ['smart', 'competition', 'research', 'resource'])
  assert.ok(calls.every(call => call.messages.length === 1))
})

test('流式回复更新同一消息，停止后清理生成状态并允许重试', async () => {
  let rejectRequest, onDelta, signal
  const chat = useAIChat((_messages, options) => {
    onDelta = options.onDelta
    signal = options.signal
    return new Promise((_resolve, reject) => { rejectRequest = reject })
  })
  const task = chat.submit('你好')
  assert.equal(chat.messages.value.length, 2)
  assert.equal(chat.messages.value[1].generating, true)
  onDelta('根据')
  onDelta('你的需求')
  assert.equal(chat.messages.value.length, 2)
  assert.equal(chat.stop(), true)
  assert.equal(signal.aborted, true)
  rejectRequest(new DOMException('aborted', 'AbortError'))
  assert.equal(await task, false)
  assert.equal(chat.pending.value, false)
  assert.equal(chat.messages.value[1].incomplete, true)
  assert.equal(chat.messages.value[1].generating, false)
  assert.equal(chat.messages.value[1].content, '根据你的需求')
})
