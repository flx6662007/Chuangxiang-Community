import test from 'node:test'
import assert from 'node:assert/strict'
import { profilePayload, registrationLabels } from '../src/utils/guide.js'

test('条件表单显式清空字段并转换数字，不将空白时间变成零', () => {
  const data = profilePayload({ skills: 'Python，写作', interests: '机器人、数学建模', weekly_hours: '', team_size: '3' })
  assert.deepEqual(data.skills, ['Python', '写作'])
  assert.deepEqual(data.interests, ['机器人', '数学建模'])
  assert.equal(data.weekly_hours, null)
  assert.equal(data.team_size, 3)
  assert.equal(data.major, '')
})
test('未知报名状态和历史截止有明确且不同的显示', () => {
  assert.equal(registrationLabels.unknown, '报名信息未收录完整')
  assert.equal(registrationLabels.closed, '该届报名已结束')
})
