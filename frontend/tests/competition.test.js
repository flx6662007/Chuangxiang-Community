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
  officialText,
  officialUnknown,
  teamSizeLabel,
  competitionOfficialLink,
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
  assert.equal(formatDeadline({}, 'registration_deadline'), officialUnknown)
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
      label: '报名截止日期',
      value: '2020-01-01（时刻以原文为准）',
    },
  )
  assert.deepEqual(
    summaryDeadline({
      registration_deadline_at: '2020-01-01T12:00:00Z',
      submission_deadline: '2030-10-31',
    }),
    {
      label: '报名截止日期',
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
      label: '作品提交截止日期',
      value: '2026-09-30（时刻以原文为准）',
    },
  )
  assert.deepEqual(
    summaryDeadline({ submission_deadline_at: '2026-09-30T12:00:00Z' }),
    {
      label: '作品提交截止日期',
      value: '2026-09-30T12:00:00Z',
    },
  )
  assert.deepEqual(summaryDeadline({}), { label: '截止时间', value: officialUnknown })
})

test('缺失字段说明本站暂未收录，不断言官方通知没有写', () => {
  assert.equal(officialUnknown, '暂未收录，请查阅原文')
  for (const value of [undefined, null, '', '  \n ', 0])
    assert.equal(officialText(value), officialUnknown)
  assert.equal(officialText('  限在校本科生\n可跨专业  '), '限在校本科生\n可跨专业')
  assert.equal(teamSizeLabel({ participation_type: 'unknown' }), officialUnknown)
  assert.equal(teamSizeLabel({ participation_type: 'team' }), officialUnknown)
  assert.equal(teamSizeLabel({ participation_type: 'individual' }), '个人参赛')
})

test('团队人数保留单侧缺项，不把教师数或未知人数补成学生人数', () => {
  assert.equal(teamSizeLabel({ team_size_max: 3 }), '至多 3 人（下限暂未收录）')
  assert.equal(teamSizeLabel({ team_size_min: 2 }), '至少 2 人（上限暂未收录）')
  assert.equal(teamSizeLabel({ team_size_min: 2, team_size_max: 5 }), '2–5 人')
  assert.equal(teamSizeLabel({ team_size_min: 3, team_size_max: 3 }), '3 人')
  assert.match(teamSizeLabel({ team_size_min: 5, team_size_max: 3 }), /待核实/)
  assert.equal(teamSizeLabel({ team_size_max: 0, teachers: 2 }), officialUnknown)
})

test('官网通知不冒充报名入口，缺少链接不造可点击按钮', () => {
  const source = { source_url: 'https://example.org/notice' }
  assert.deepEqual(competitionOfficialLink({ primary_source: source }), {
    url: source.source_url, label: '查看官方通知',
  })
  assert.deepEqual(competitionOfficialLink({
    primary_source: source, registration_url: source.source_url + '#registration',
  }), {
    url: source.source_url + '#registration', label: '查看官方通知',
  })
  assert.deepEqual(competitionOfficialLink({
    primary_source: source, registration_url: 'https://registration.example.org/',
  }), {
    url: 'https://registration.example.org/', label: '查看官方报名页面',
  })
  assert.equal(competitionOfficialLink({}), null)
  assert.equal(competitionOfficialLink({ registration_url: 'javascript:alert(1)' }), null)
  assert.deepEqual(competitionOfficialLink({
    registration_url: 'javascript:alert(1)', sources: [source],
  }), { url: source.source_url, label: '查看官方通知' })
})

test('时效状态不通过报名日期或组队开放猜测；缺少后端依据保持未知', () => {
  assert.match(
    deadlineStatusLabel({
      registration_deadline: '2030-01-01',
      is_recruitment_open: true,
    }),
    /暂未收录/,
  )
  assert.match(deadlineStatusLabel({ deadline_status: 'open' }), /暂未收录/)
  assert.equal(
    deadlineStatusLabel({
      deadline_status: 'open',
      deadline_status_label: '尚未到报名截止日期',
    }),
    '尚未到报名截止日期',
  )
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
      deadline_status_label: '尚未到作品提交截止日期；报名时间未明确',
    }),
    '尚未到作品提交截止日期；报名时间未明确',
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
