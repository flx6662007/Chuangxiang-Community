export const governanceTargetLabels = {
  competition: '赛事信息',
  recruitment: '招募信息',
  restriction: '账号限制',
  recruitment_action: '招募处置',
  report: '举报处理结果',
}
export const descriptionLimit = 1000
export function descriptionError(value) {
  const text = typeof value === 'string' ? value.trim() : ''
  if (!text) return '请填写具体说明。'
  if (Array.from(text).length > descriptionLimit)
    return '说明不能超过 1000 字。'
  return ''
}
export function targetKey(target) {
  if (
    !target ||
    !['restriction', 'recruitment_action', 'report'].includes(
      target.target_type,
    )
  )
    return ''
  const id = Number(target.target_id)
  return Number.isSafeInteger(id) && id > 0 ? target.target_type + ':' + id : ''
}
export function availableAppealTarget(items, key) {
  if (!key) return null
  return (
    items.find(
      (item) =>
        targetKey(item) === key &&
        item.can_appeal === true &&
        !item.pending_appeal_id,
    ) || null
  )
}
export function appealInput(items, key, description) {
  const target = availableAppealTarget(items, key)
  if (!target)
    throw new Error('该事项当前不可申诉，请刷新可申诉事项后重新选择。')
  const error = descriptionError(description)
  if (error) throw new Error(error)
  return {
    target_type: target.target_type,
    target_id: Number(target.target_id),
    description: description.trim(),
  }
}
export function governanceError(error) {
  const status = error.response?.status
  const body = error.response?.data
  if (!status)
    return '网络连接失败，请重试；提交结果不确定时，请先查看本人记录。'
  if (status >= 500) return '服务暂时不可用，请稍后重试。'
  if (status === 429) return '提交过于频繁，请稍后再试。'
  if (
    body?.code === 'csrf_failed' ||
    (typeof body?.detail === 'string' && body.detail.startsWith('CSRF Failed:'))
  )
    return '页面凭据失效，请刷新页面后重试。'
  if (status === 401 || status === 403)
    return '请刷新登录状态后重试。举报和申诉无需邮箱核验。'
  if (status === 404) return '记录不存在或当前账号无法查看，请刷新本人记录。'
  if (typeof body?.detail === 'string') return body.detail
  const labels = {
    target_type: '事项类型',
    target_id: '相关事项',
    reason: '举报原因',
    description: '说明',
    non_field_errors: '提交内容',
  }
  const fields = body?.fields || body || {}
  const messages = Object.entries(fields).flatMap(([field, values]) =>
    (Array.isArray(values) ? values : [values])
      .filter((value) => typeof value === 'string')
      .map((value) => (labels[field] || field) + '：' + value),
  )
  if (messages.length) return messages.join('；')
  if (status === 409) return '同一事项已有待处理记录或状态已变化，请刷新查看。'
  return '提交未完成，请检查内容后重试。'
}
