import test from 'node:test'
import assert from 'node:assert/strict'
import {
  applicationInput,
  applicationVersionPayload,
  can,
  cleanRecruitmentInput,
  notificationTarget,
  teamError,
  validPage,
  withHistoricalOptions,
} from '../src/utils/teams.js'

test('写招募只提交模板白名单，线上协作清掉旧校区且不携带联系方式', () => {
  const result = cleanRecruitmentInput({
    existing_member_count: '2',
    recruitment_quota: '3',
    collaboration_mode: 'online',
    campuses: [{ code: 'campus-a', name: 'A校区' }],
    required_roles: [{ code: 'developer', name: '开发' }],
    email: 'private@example.org',
    phone_number: '123',
    allowed_actions: ['edit'],
    version: 7,
  })
  assert.equal(result.existing_member_count, 2)
  assert.equal(result.recruitment_quota, 3)
  assert.deepEqual(result.campuses, [])
  assert.deepEqual(result.required_roles, ['developer'])
  assert.equal('email' in result, false)
  assert.equal('phone_number' in result, false)
  assert.equal('allowed_actions' in result, false)
  assert.equal('version' in result, false)
})

test('继续申请更新资料而不沿用确认，版本令牌使用当前卡片而非旧接受版本', () => {
  const application = {
    version: 4,
    recruitment_version: 1,
    recruitment: { version: 6 },
    skills: [{ code: 'python', name: 'Python' }],
    desired_roles: [],
    weekly_effort: 'over_2_to_5',
    applicant_confirmed_at: '2026-09-26',
    contact_available: true,
  }
  assert.deepEqual(applicationVersionPayload(application), {
    expected_version: 6,
    expected_application_version: 4,
  })
  assert.deepEqual(applicationInput(application), {
    skills: ['python'],
    desired_roles: [],
    weekly_effort: 'over_2_to_5',
  })
})

test('可见按钮只能来自当前服务端允许动作，未知缺省不能自行授权', () => {
  assert.equal(can({ status: 'open' }, 'apply'), false)
  assert.equal(can({ allowed_actions: ['withdraw'] }, 'confirm'), false)
  assert.equal(can({ allowed_actions: ['withdraw'] }, 'withdraw'), true)
  assert.equal(can(null, 'edit'), false)
})

test('业务错误保留具体字段和版本原因，服务端异常不暴露内部内容', () => {
  assert.match(
    teamError({
      response: {
        status: 409,
        data: { code: 'stale_version', detail: '卡片版本已变化' },
      },
    }),
    /版本已变化/,
  )
  assert.match(
    teamError({
      response: {
        status: 400,
        data: {
          detail: '请检查提交字段',
          fields: { weekly_effort: ['请选择投入区间'] },
        },
      },
    }),
    /每周投入：请选择投入区间/,
  )
  assert.equal(
    teamError({
      response: { status: 500, data: { detail: 'private traceback' } },
    }),
    '服务暂时不可用，请稍后重试。',
  )
})

test('通知仅映射已知站内目标，不能打开响应中附带的任意网址', () => {
  assert.deepEqual(notificationTarget({ type: 'application', id: 3 }), {
    name: 'my-teams',
    query: { tab: 'sent', application: 3 },
  })
  assert.deepEqual(notificationTarget({ type: 'recruitment', id: 8 }), {
    name: 'recruitment-detail',
    params: { id: 8 },
  })
  assert.deepEqual(
    notificationTarget({ type: 'url', id: 'https://example.org' }),
    { name: 'my-teams' },
  )
  assert.deepEqual(
    notificationTarget({ type: 'recruitment', id: '../../account' }),
    { name: 'my-teams' },
  )
})

test('分页拒绝非整数或异常值而不把未授权 URL 当下一页请求', () => {
  assert.equal(validPage('3'), 3)
  for (const input of ['-1', '0', '2.5', 'https://example.org', '1e100'])
    assert.equal(validPage(input), 1)
})

test('停用历史选项保留但不重复，新字段不能将其当作可新增词条', () => {
  const options = withHistoricalOptions(
    [{ code: 'python', name: 'Python' }],
    [
      { code: 'old', name: '旧技能' },
      { code: 'old', name: '旧技能' },
      { code: 'python', name: 'Python' },
    ],
  )
  assert.equal(options.length, 2)
  assert.equal(options[1].inactive, true)
  assert.equal(options[1].name, '旧技能（已停用）')
  assert.equal(options[0].inactive, undefined)
})

import { recruitmentDeadline } from '../src/utils/teams.js'

test('招募实际截止优先使用赛事更正后的时刻，旧接口仍回退首次期限', () => {
  assert.equal(
    recruitmentDeadline({
      effective_expires_at: '2026-10-01T12:00:00+08:00',
      expires_at: '2026-10-07T12:00:00+08:00',
    }),
    '2026-10-01T12:00:00+08:00',
  )
  assert.equal(
    recruitmentDeadline({ expires_at: '2026-10-07T12:00:00+08:00' }),
    '2026-10-07T12:00:00+08:00',
  )
  assert.equal(
    recruitmentDeadline({
      effective_expires_at: null,
      expires_at: '2026-10-07T12:00:00+08:00',
    }),
    '2026-10-07T12:00:00+08:00',
  )
  assert.equal(recruitmentDeadline({}), null)
})
