export const levelLabels = {
  unknown: '范围暂未收录',
  international: '国际',
  national: '全国',
  provincial: '省级',
  municipal: '市级',
  university: '校级',
  college: '院系级',
  other: '其他',
}

export const participationLabels = {
  unknown: '参赛形式暂未收录',
  individual: '个人赛',
  team: '团队赛',
  both: '个人或团队',
}

export const officialUnknown = '未收录'

export function officialText(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : officialUnknown
}

// 单边人数限制保留缺失边界，不能把未知下限自动补为 1。
export function teamSizeLabel(record) {
  const minimum = record.team_size_min
  const maximum = record.team_size_max
  const hasMin = Number.isInteger(minimum) && minimum > 0
  const hasMax = Number.isInteger(maximum) && maximum > 0
  if (hasMin && hasMax) {
    if (minimum > maximum) return '人数信息待核实，请查阅官方通知'
    return minimum === maximum ? `${minimum} 人` : `${minimum}–${maximum} 人`
  }
  if (hasMin) return `至少 ${minimum} 人（上限暂未收录）`
  if (hasMax) return `至多 ${maximum} 人（下限暂未收录）`
  return record.participation_type === 'individual' ? '个人参赛' : officialUnknown
}

// 外部网址只接受明确的 HTTP(S) 地址，不把来源内容作为 HTML 执行。
export function safeExternalUrl(value) {
  if (typeof value !== 'string') return ''
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : ''
  } catch {
    return ''
  }
}

// 来源网页只用于查看通知；有独立报名网址时才使用报名页面标签。
export function competitionOfficialLink(record) {
  const sources = [record.primary_source, ...(record.sources || [])]
    .map((source) => safeExternalUrl(source?.source_url))
    .filter(Boolean)
  const registration = safeExternalUrl(record.registration_url)
  if (registration) {
    const sameSource = sources.some(
      (source) => source.split('#')[0] === registration.split('#')[0],
    )
    return {
      url: registration,
      label: sameSource ? '查看官方通知' : '查看官方报名页面',
    }
  }
  return sources.length ? { url: sources[0], label: '查看官方通知' } : null
}

export function formatDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? value
    : '未注明'
}

// 日历日期不能被当成当地午夜；只有明确时刻才进行时区转换。
export function formatDeadline(record, field) {
  const day = formatDate(record[field])
  const instant = record[`${field}_at`]
  const zone = record[`${field}_timezone`]
  if (!instant) return day === '未注明' ? officialUnknown : day
  const date = new Date(instant)
  if (Number.isNaN(date.getTime())) return `${day}（时刻待核实）`
  if (zone) {
    try {
      const formatted = new Intl.DateTimeFormat('zh-CN', {
        timeZone: zone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h23',
      }).format(date)
      return `${formatted}（${zone}）`
    } catch {
      // 部分浏览器不支持固定偏移时区，显示接口原始带偏移时间，避免猜测。
    }
  }
  return `${instant}${zone ? `（来源时区 ${zone}）` : ''}`
}

// 保留截止类型：后续作品提交日期不能掩盖已经截止的报名日期。
export function summaryDeadline(record) {
  if (record.registration_deadline || record.registration_deadline_at) {
    return {
      label: '报名截止日期',
      value: formatDeadline(record, 'registration_deadline'),
    }
  }
  if (record.submission_deadline || record.submission_deadline_at) {
    return {
      label: '作品提交截止日期',
      value: formatDeadline(record, 'submission_deadline'),
    }
  }
  return { label: '截止时间', value: officialUnknown }
}

export function formatUpdatedAt(value) {
  if (!value) return '未注明'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未注明'
  return (
    new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).format(date) + '（北京时间）'
  )
}

export const competitionTimeOptions = [
  { code: 'current', name: '当前' },
  { code: 'expired', name: '历史' },
  { code: 'all', name: '全部' },
]

export function normalizeTimeStatus(value) {
  return competitionTimeOptions.some((item) => item.code === value)
    ? value
    : 'current'
}

export function competitionListQuery({
  search = '',
  category = '',
  timeStatus = 'current',
  page = 1,
} = {}) {
  const status = normalizeTimeStatus(timeStatus)
  return {
    ...(search ? { search } : {}),
    ...(category ? { category } : {}),
    ...(status !== 'current' ? { time_status: status } : {}),
    ...(Number.isSafeInteger(page) && page > 1 ? { page } : {}),
  }
}

// 以服务端时效为准；缺少状态或只有组队资格时，不能推断为正在报名。
export function deadlineStatusLabel(record) {
  if (
    ['open', 'closed', 'unknown'].includes(record.deadline_status) &&
    typeof record.deadline_status_label === 'string' &&
    record.deadline_status_label.trim()
  ) {
    return record.deadline_status_label
  }
  return record.deadline_status === 'closed'
    ? '已截止'
    : '截止时间暂未收录，请查阅原文'
}
