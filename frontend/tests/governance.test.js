import test from 'node:test'
import assert from 'node:assert/strict'
import {
  appealInput,
  availableAppealTarget,
  descriptionError,
  governanceError,
  targetKey,
} from '../src/utils/governance.js'
import { createSessionFence } from '../src/utils/sessionEvents.js'

test('申诉只接受当前本人事项列表中的可申诉对象，不接受任意ID、待处理或失效记录', () => {
  const targets = [
    {
      target_type: 'restriction',
      target_id: 7,
      can_appeal: true,
      pending_appeal_id: null,
      reason: '不应回传',
      email: 'private@example.org',
    },
    {
      target_type: 'report',
      target_id: 9,
      can_appeal: true,
      pending_appeal_id: 3,
    },
    { target_type: 'report', target_id: 10, can_appeal: false },
  ]
  assert.deepEqual(
    appealInput(targets, 'restriction:7', '  请复核事实依据  '),
    { target_type: 'restriction', target_id: 7, description: '请复核事实依据' },
  )
  for (const key of [
    'restriction:8',
    'report:9',
    'report:10',
    'https://example.org',
    '',
  ]) {
    assert.equal(availableAppealTarget(targets, key), null)
    assert.throws(() => appealInput(targets, key, '说明'), /不可申诉/)
  }
  assert.equal(targetKey({ target_type: 'recruitment', target_id: 7 }), '')
  assert.equal(targetKey({ target_type: 'report', target_id: '../7' }), '')
})

test('说明拒绝空白和超长，1000字符边界可以提交', () => {
  assert.ok(descriptionError(' ' + String.fromCharCode(10) + '  '))
  assert.ok(descriptionError('中'.repeat(1001)))
  assert.equal(descriptionError('中'.repeat(1000)), '')
  assert.throws(
    () =>
      appealInput(
        [{ target_type: 'report', target_id: 1, can_appeal: true }],
        'report:1',
        '',
      ),
    /填写具体说明/,
  )
})

test('退出、换号或隐藏后旧请求与旧表单响应均不可重新展示', () => {
  const fence = createSessionFence()
  const oldRead = fence.capture(),
    oldWrite = fence.capture()
  fence.invalidate()
  const currentRead = fence.capture()
  assert.equal(fence.isCurrent(oldRead), false)
  assert.equal(fence.isCurrent(oldWrite), false)
  assert.equal(fence.isCurrent(currentRead), true)
  fence.invalidate()
  assert.equal(fence.isCurrent(currentRead), false)
})

test('治理错误不要求核验邮箱，不披露服务端异常，并提示重复与频率限制', () => {
  assert.match(governanceError({ response: { status: 403 } }), /无需邮箱核验/)
  assert.match(
    governanceError({
      response: { status: 409, data: { detail: '已有待处理举报' } },
    }),
    /已有待处理举报/,
  )
  assert.match(governanceError({ response: { status: 429 } }), /过于频繁/)
  assert.equal(
    governanceError({
      response: { status: 500, data: { detail: 'secret traceback' } },
    }),
    '服务暂时不可用，请稍后重试。',
  )
})
