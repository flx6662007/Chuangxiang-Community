export const levelLabels = {
  unknown: '范围未注明', international: '国际', national: '全国',
  provincial: '省级', municipal: '市级', university: '校级', college: '院系级', other: '其他',
}

export const participationLabels = {
  unknown: '参赛形式未说明', individual: '个人赛', team: '团队赛', both: '个人或团队',
}

// 外部网址只接受明确的 HTTP(S) 地址，不把来源内容作为 HTML 执行。
export function safeExternalUrl(value) {
  if (typeof value !== 'string') return ''
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''
  } catch {
    return ''
  }
}

export function formatDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : '未注明'
}

// 日历日期不能被当成当地午夜；只有明确时刻才进行时区转换。
export function formatDeadline(record, field) {
  const day = formatDate(record[field])
  const instant = record[`${field}_at`]
  const zone = record[`${field}_timezone`]
  if (!instant) return day === '未注明' ? day : `${day}（未注明时刻）`
  const date = new Date(instant)
  if (Number.isNaN(date.getTime())) return `${day}（时刻待核实）`
  if (zone) {
    try {
      const formatted = new Intl.DateTimeFormat('zh-CN', {
        timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
      }).format(date)
      return `${formatted}（${zone}）`
    } catch {
      // 部分浏览器不支持固定偏移时区，显示接口原始带偏移时间，避免猜测。
    }
  }
  return `${instant}${zone ? `（来源时区 ${zone}）` : ''}`
}

export function formatUpdatedAt(value) {
  if (!value) return '未注明'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未注明'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(date) + '（北京时间）'
}
