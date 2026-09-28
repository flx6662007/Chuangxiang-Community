import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatDeadline,
  formatUpdatedAt,
  safeExternalUrl,
  summaryDeadline,
  deadlineStatusLabel,
  normalizeTimeStatus,
  competitionListQuery,
} from '../src/utils/competition.js'

test('外部链接只开放 HTTP(S)，拒绝脚本、相对地址和含凭据地址', () => {
  assert.equal(
    safeExternalUrl('https://example.com/notice'),
    'https://example.com/notice',
  )
  for (const value of [
    'javascript:alert(1)',
    'data:text/html,hello',
    '/notice',
    '//example.com',
    'https://name:password@example.com',
    null,
  ]) {
    assert.equal(safeExternalUrl(value), '')
  }
})

test('未记录精确时刻时保持日历日期并提示查阅原文，不假定午夜或 23:59', () => {
  assert.equal(
    formatDeadline(
      { registration_deadline: '2026-10-15' },
      'registration_deadline',
    ),
    '2026-10-15（时刻以原文为准）',
  )
  assert.equal(
    formatDeadline(
      {
        registration_deadline: '2026-10-15',
        deadline_notes: '报名截止时间为 2026年10月15日20:00',
      },
      'registration_deadline',
    ),
    '2026-10-15（时刻以原文为准）',
  )
  assert.equal(formatDeadline({}, 'registration_deadline'), '未注明')
})

test('明确时刻按来源时区显示，不能跟随浏览器所在地变动', () => {
  const record = {
    registration_deadline: '2026-10-15',
    registration_deadline_at: '2026-10-15T12:00:00Z',
    registration_deadline_timezone: 'Asia/Shanghai',
  }
  const text = formatDeadline(record, 'registration_deadline')
  assert.match(text, /2026\/10\/15.*20:00:00.*Asia\/Shanghai/)
  assert.match(formatUpdatedAt('2026-10-15T12:00:00Z'), /20:00.*北京时间/)
})

test('无法识别来源时区时保留带偏移原始时刻，不虚构时区转换', () => {
  assert.equal(
    formatDeadline(
      {
        registration_deadline: '2026-10-15',
        registration_deadline_at: '2026-10-15T12:00:00Z',
        registration_deadline_timezone: 'invalid-zone',
      },
      'registration_deadline',
    ),
    '2026-10-15T12:00:00Z（来源时区 invalid-zone）',
  )
})

test('卡片始终优先报名截止，不能被更晚作品日期覆盖', () => {
  assert.deepEqual(
    summaryDeadline({
      registration_deadline: '2020-01-01',
      submission_deadline: '2030-10-31',
    }),
    {
      label: '报名截止',
      value: '2020-01-01（时刻以原文为准）',
    },
  )
  assert.deepEqual(
    summaryDeadline({
      registration_deadline_at: '2020-01-01T12:00:00Z',
      submission_deadline: '2030-10-31',
    }),
    {
      label: '报名截止',
      value: '2020-01-01T12:00:00Z',
    },
  )
})

test('只有作品投稿日期时用准确标签和原日期，不虚构报名时刻', () => {
  assert.deepEqual(
    summaryDeadline({
      registration_deadline: null,
      submission_deadline: '2026-09-30',
    }),
    {
      label: '作品提交截止',
      value: '2026-09-30（时刻以原文为准）',
    },
  )
  assert.deepEqual(
    summaryDeadline({ submission_deadline_at: '2026-09-30T12:00:00Z' }),
    {
      label: '作品提交截止',
      value: '2026-09-30T12:00:00Z',
    },
  )
  assert.deepEqual(summaryDeadline({}), { label: '截止时间', value: '未注明' })
})

test('时效状态不通过报名日期或组队开放猜测；缺少后端依据保持未知', () => {
  assert.match(
    deadlineStatusLabel({
      registration_deadline: '2030-01-01',
      is_recruitment_open: true,
    }),
    /未明确/,
  )
  assert.match(deadlineStatusLabel({ deadline_status: 'open' }), /未明确/)
  assert.equal(
    deadlineStatusLabel({
      deadline_status: 'closed',
      deadline_status_label: '报名已截止',
      submission_deadline: '2030-01-01',
    }),
    '报名已截止',
  )
  assert.equal(
    deadlineStatusLabel({
      deadline_status: 'open',
      deadline_status_label: '作品提交未截止；报名时间未明确',
    }),
    '作品提交未截止；报名时间未明确',
  )
})

test('赛事时效筛选安全归一化并保留历史搜索、分类和页码', () => {
  for (const value of [undefined, '', 'open', ['expired'], 'CURRENT'])
    assert.equal(normalizeTimeStatus(value), 'current')
  assert.equal(normalizeTimeStatus('expired'), 'expired')
  assert.equal(normalizeTimeStatus('all'), 'all')
  assert.deepEqual(
    competitionListQuery({
      search: '机器人',
      category: 'engineering',
      timeStatus: 'expired',
      page: 3,
    }),
    {
      search: '机器人',
      category: 'engineering',
      time_status: 'expired',
      page: 3,
    },
  )
  assert.deepEqual(
    competitionListQuery({ search: '机器人', timeStatus: 'all' }),
    { search: '机器人', time_status: 'all' },
  )
  assert.deepEqual(competitionListQuery({ timeStatus: 'current', page: 1 }), {})
})
