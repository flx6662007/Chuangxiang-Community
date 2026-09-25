import test from 'node:test'
import assert from 'node:assert/strict'
import { formatDeadline, formatUpdatedAt, safeExternalUrl } from '../src/utils/competition.js'

test('外部链接只开放 HTTP(S)，拒绝脚本、相对地址和含凭据地址', () => {
  assert.equal(safeExternalUrl('https://example.com/notice'), 'https://example.com/notice')
  for (const value of ['javascript:alert(1)', 'data:text/html,hello', '/notice', '//example.com', 'https://name:password@example.com', null]) {
    assert.equal(safeExternalUrl(value), '')
  }
})

test('日期未注明时刻时保持日历日期，不假定午夜或 23:59', () => {
  assert.equal(formatDeadline({ registration_deadline: '2026-10-15' }, 'registration_deadline'), '2026-10-15（未注明时刻）')
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
  assert.equal(formatDeadline({
    registration_deadline: '2026-10-15',
    registration_deadline_at: '2026-10-15T12:00:00Z',
    registration_deadline_timezone: 'invalid-zone',
  }, 'registration_deadline'), '2026-10-15T12:00:00Z（来源时区 invalid-zone）')
})
