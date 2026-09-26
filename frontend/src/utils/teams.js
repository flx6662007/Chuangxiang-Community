export const labels = {
  beginner_ok: '接受零基础',
  introductory: '具备入门基础',
  project_experience: '有项目经验',
  up_to_2: '每周 2 小时以内',
  over_2_to_5: '每周 2–5 小时',
  over_5_to_10: '每周 5–10 小时',
  over_10: '每周 10 小时以上',
  online: '线上协作',
  offline: '线下协作',
  hybrid: '线上与线下结合',
  learning: '学习积累',
  deliver_entry: '完成参赛作品',
  strong_result: '争取较好成绩',
  up_to_1_month: '1 个月以内',
  over_1_to_3_months: '1–3 个月',
  over_3_to_6_months: '3–6 个月',
  over_6_months: '6 个月以上',
  open: '正在招募',
  closed: '已结束',
  paused: '暂缓招募',
  unavailable: '不可申请',
  pending: '待处理',
  contact_open: '已开放联系，待双方确认',
  joined: '已正式入队',
  withdrawn: '已撤回',
  rejected: '已拒绝',
  ended: '已结束',
  approved: '已同意',
  timed_out: '24 小时未回应，已完成',
  completed: '已完成',
  team_dissolved: '队伍已解散',
  expired: '招募到期',
  full: '名额已满',
  manual: '主动关闭',
  card_closed: '招募关闭',
  card_withdrawn: '招募下架',
  competition_stopped: '赛事停止招募',
  competition_withdrawn: '赛事下架',
  joined_other_team: '已加入同届另一队',
  recruiter_terminated: '招募者结束申请',
  account_disabled: '账号停用',
  exit: '退出队伍',
  removal: '移除成员',
  dissolution: '队伍解散',
}
export const fieldLabels = {
  existing_member_count: '已有成员数',
  recruitment_quota: '计划招募人数',
  current_skills: '已有能力',
  required_roles: '所需角色',
  required_skills: '所需技能',
  foundation_requirement: '基础要求',
  weekly_effort: '每周投入',
  collaboration_mode: '协作方式',
  collaboration_goal: '合作目标',
  expected_duration: '合作时长',
  campuses: '协作校区',
  competition: '所属赛事',
  duration_days: '有效期',
  desired_roles: '意向角色',
  skills: '已有技能',
  expected_version: '卡片版本',
}
export const actionLabels = {
  accept: '接受并开放联系',
  reject: '拒绝申请',
  withdraw: '撤回申请',
  end: '结束申请',
  confirm: '确认正式入队',
  'revoke-confirmation': '撤销本人确认',
  continue: '按最新条件继续',
}
export function label(value) {
  return labels[value] || value || '未选择'
}
export function can(item, action) {
  return (
    Array.isArray(item?.allowed_actions) &&
    item.allowed_actions.includes(action)
  )
}
export function optionNames(options) {
  return options?.map((item) => item.name).join('、') || '未选择'
}
export function optionCodes(options) {
  return (
    options?.map((item) => (typeof item === 'string' ? item : item.code)) || []
  )
}
export function teamError(error) {
  const status = error.response?.status
  const body = error.response?.data
  if (!status) return '网络连接失败，请检查网络后重试。'
  if (status >= 500) return '服务暂时不可用，请稍后重试。'
  if (status === 429) return '操作过于频繁，请稍后再试。'
  if (body?.code === 'csrf_failed') return '页面凭据失效，请刷新页面后重试。'
  if (body?.fields && typeof body.fields === 'object') {
    const messages = Object.entries(body.fields).flatMap(([key, value]) =>
      (Array.isArray(value) ? value : [value])
        .filter((v) => typeof v === 'string')
        .map((v) => `${fieldLabels[key] || key}：${v}`),
    )
    if (messages.length) return messages.join('；')
  }
  if (typeof body?.detail === 'string') return body.detail
  if (status === 401 || status === 403)
    return '请检查登录、邮箱核验状态和操作权限。'
  if (status === 409)
    return '内容或状态已变化，请加载最新内容并重新核对后操作。'
  if (status === 404) return '记录不存在、不可访问或这一页已失效。'
  const messages = Object.entries(body || {}).flatMap(([key, value]) =>
    (Array.isArray(value) ? value : [value])
      .filter((v) => typeof v === 'string')
      .map((v) => `${fieldLabels[key] || key}：${v}`),
  )
  return messages.join('；') || '操作未完成，请检查输入后重试。'
}
export function recruitmentInput(revision = {}) {
  return {
    existing_member_count: revision.existing_member_count ?? 1,
    recruitment_quota: revision.recruitment_quota ?? 1,
    foundation_requirement: revision.foundation_requirement || '',
    weekly_effort: revision.weekly_effort || '',
    collaboration_mode: revision.collaboration_mode || '',
    collaboration_goal: revision.collaboration_goal || '',
    expected_duration: revision.expected_duration || '',
    current_skills: optionCodes(revision.current_skills),
    required_roles: optionCodes(revision.required_roles),
    required_skills: optionCodes(revision.required_skills),
    campuses: optionCodes(revision.campuses),
  }
}
export function applicationInput(revision = {}) {
  return {
    desired_roles: optionCodes(revision.desired_roles),
    skills: optionCodes(revision.skills),
    weekly_effort: revision.weekly_effort || '',
  }
}
// 不复用公开对象的任意字段，尤其不把联系方式和旧确认带回写请求。
export function cleanRecruitmentInput(form) {
  const result = recruitmentInput(form)
  if (result.collaboration_mode === 'online') result.campuses = []
  result.existing_member_count = Number(result.existing_member_count)
  result.recruitment_quota = Number(result.recruitment_quota)
  return result
}
export function validPage(value) {
  const page = Number(value)
  return Number.isSafeInteger(page) && page > 0 ? page : 1
}
export function applicationVersionPayload(item) {
  return {
    expected_version: item.recruitment.version,
    expected_application_version: item.version,
  }
}
export function notificationTarget(target) {
  if (
    target?.type === 'application' &&
    Number.isSafeInteger(Number(target.id)) &&
    Number(target.id) > 0
  )
    return { name: 'my-teams', query: { tab: 'sent', application: target.id } }
  if (
    target?.type === 'recruitment' &&
    Number.isSafeInteger(Number(target.id)) &&
    Number(target.id) > 0
  )
    return { name: 'recruitment-detail', params: { id: target.id } }
  return { name: 'my-teams' }
}

export function withHistoricalOptions(active = [], historical = []) {
  const codes = new Set(active.map((option) => option.code))
  const result = [...active]
  for (const option of historical) {
    if (!codes.has(option.code)) {
      codes.add(option.code)
      result.push({
        ...option,
        name: option.name + '（已停用）',
        inactive: true,
      })
    }
  }
  return result
}

// 赛事截止更正可能提前实际截止；首次发布期限仍保留作历史。
export function recruitmentDeadline(card) {
  return card?.effective_expires_at || card?.expires_at || null
}
