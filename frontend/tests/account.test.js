import test from 'node:test'
import assert from 'node:assert/strict'
import { csrfFromCookie, isPendingPasswordReset, isFinishedPasswordReset, isSignedOut, accountErrorMessages, withProfileSessionCheck } from '../src/utils/account.js'

const response = (flows) => ({ status: 401, meta: { is_authenticated: false }, data: { flows } })

test('CSRF 从当前 cookie 精确取值，轮换后读取新值', () => {
  assert.equal(csrfFromCookie('othercsrftoken=wrong; csrftoken=old'), 'old')
  assert.equal(csrfFromCookie('sessionid=private; csrftoken=new'), 'new')
  assert.equal(csrfFromCookie('sessionid=private'), '')
  assert.equal(csrfFromCookie('csrftoken=%broken'), '')
})

test('找回密码的 401 必须带 pending reset 流程，普通未登录不能冒充已发信', () => {
  assert.equal(isPendingPasswordReset(response([{ id: 'login' }])), false)
  assert.equal(isPendingPasswordReset(response([{ id: 'password_reset_by_code', is_pending: true }])), true)
  assert.equal(isPendingPasswordReset({ status: 401 }), false)
})

test('重置完成必须已退出且无待处理 reset 流程', () => {
  const completed = response([{ id: 'login' }, { id: 'password_reset_by_code', is_pending: false }])
  assert.equal(isSignedOut(completed), true)
  assert.equal(isFinishedPasswordReset(completed), true)
  assert.equal(isFinishedPasswordReset(response([{ id: 'login' }, { id: 'password_reset_by_code', is_pending: true }])), false)
  assert.equal(isFinishedPasswordReset({ status: 401 }), false)
})

test('CSRF 失效与发信权限错误分开提示，不显示服务端 500 内容', () => {
  assert.match(accountErrorMessages({ response: { status: 403, data: { code: 'csrf_failed' } } })[0], /刷新/)
  assert.match(accountErrorMessages({ response: { status: 403, data: { status: 403 } } }, 'send')[0], /重发次数/)
  assert.doesNotMatch(accountErrorMessages({ response: { status: 403, data: {} } })[0], /验证码|重发/)
  assert.deepEqual(accountErrorMessages({ response: { status: 500, data: { detail: 'private traceback' } } }), ['服务暂时不可用，请稍后重试。'])
})

test('资料请求被拒后检查会话，确认已退出才通知页面清空旧资料', async () => {
  const failure = { response: { status: 403, data: { detail: 'Authentication credentials were not provided.' } } }
  let checks = 0
  await assert.rejects(withProfileSessionCheck(
    async () => { throw failure },
    async () => { checks++; return { status: 401, data: response([{ id: 'login' }]) } },
  ), (error) => {
    assert.equal(error.sessionExpired, true)
    assert.equal(error.accountContext, 'profile')
    assert.deepEqual(accountErrorMessages(error), ['登录状态已失效，请重新登录。'])
    return true
  })
  assert.equal(checks, 1)
})

test('资料 403 但会话仍有效时保留登录态，CSRF 错误仍提示刷新', async () => {
  const failure = { response: { status: 403, data: { detail: 'CSRF Failed: CSRF token missing.' } } }
  await assert.rejects(withProfileSessionCheck(
    async () => { throw failure },
    async () => ({ status: 200, data: { status: 200, meta: { is_authenticated: true } } }),
  ), (error) => {
    assert.equal(error.sessionExpired, false)
    assert.match(accountErrorMessages(error)[0], /页面凭据.*刷新/)
    return true
  })
})

test('会话检查网络失败不能冒充已退出，也不能误报验证码配额', async () => {
  const failure = { response: { status: 403, data: {} } }
  await assert.rejects(withProfileSessionCheck(
    async () => { throw failure },
    async () => { throw new Error('network unavailable') },
  ), (error) => {
    assert.notEqual(error.sessionExpired, true)
    assert.match(accountErrorMessages(error)[0], /账号资料/)
    assert.doesNotMatch(accountErrorMessages(error)[0], /验证码|重发/)
    return true
  })
})

test('资料字段校验失败不触发额外会话请求', async () => {
  const failure = { response: { status: 400, data: { phone_number: ['请输入有效手机号。'] } } }
  await assert.rejects(withProfileSessionCheck(
    async () => { throw failure },
    async () => { assert.fail('不应检查会话') },
  ), (error) => {
    assert.equal(error, failure)
    assert.deepEqual(accountErrorMessages(error), ['手机号：请输入有效手机号。'])
    return true
  })
})
