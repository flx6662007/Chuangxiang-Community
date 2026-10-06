export function profilePayload(form) {
  const split = value => String(value || '').split(/[、,，]/).map(x => x.trim()).filter(Boolean)
  return {
    education: form.education || null, grade: form.grade || null, major: form.major || '',
    interests: split(form.interests), skills: split(form.skills), role: form.role || '',
    weekly_hours: form.weekly_hours === '' || form.weekly_hours == null ? null : Number(form.weekly_hours),
    team_size: form.team_size === '' || form.team_size == null ? null : Number(form.team_size),
    collaboration_mode: form.collaboration_mode || null,
  }
}

export const conditionLabels = { matched: '符合已记录条件', unmatched: '条件不符合', unknown: '条件尚未确认完整' }
export const registrationLabels = { open: '报名开放', closed: '该届报名已结束', upcoming: '该届报名尚未开始', unknown: '报名信息未收录完整' }
