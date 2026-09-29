import test from 'node:test'
import assert from 'node:assert/strict'
import { accountOverview } from '../src/utils/accountOverview.js'

const profile = (reasons, eligible = false, extra = {}) => ({
  school_email_verified: true,
  has_contact_details: true,
  account_eligibility: { eligible, reasons },
  ...extra,
})

test('账户总览按真实资格原因指向优先的下一步', () => {
  assert.equal(accountOverview(profile(['email_unverified'], false, { school_email_verified: false })).title, '验证学校邮箱')
  assert.equal(accountOverview(profile(['contact_required'], false, { has_contact_details: false })).title, '补充联系方式')
  assert.equal(accountOverview(profile([], true)).title, '浏览团队广场')
  assert.equal(accountOverview(profile(['account_restricted', 'email_unverified'])).title, '查看账号限制说明')
  assert.equal(accountOverview(profile(['account_disabled'])).status, '账号已停用')
})

test('缺失或未知资格数据不能误报具备发布申请基础资格', () => {
  assert.equal(accountOverview(profile([], false)).status, '状态待核实')
  assert.equal(accountOverview({ school_email_verified: true, has_contact_details: true }).status, '状态待核实')
  assert.equal(accountOverview(null), null)
})
