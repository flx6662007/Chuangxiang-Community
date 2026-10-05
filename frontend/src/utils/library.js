// 目录身份与当届报名记录分开；这些值只整理查询，不推断报名状态。
export function libraryPage(value) {
  const page = Number(value)
  return Number.isSafeInteger(page) && page > 0 ? page : 1
}

export function libraryText(value) {
  return typeof value === 'string' ? value.trim().slice(0, 200) : ''
}

export function libraryQuery(values) {
  return Object.fromEntries(Object.entries(values).filter(([, value]) =>
    value !== '' && value !== undefined && value !== null && value !== false,
  ))
}

// 学习资源是公开浏览页，不继承目录内部预览的查询参数。
export function publicResourceQuery(values = {}) {
  return Object.fromEntries(Object.entries(values).filter(([key]) => key !== 'preview'))
}

export function resourceIcon(category) {
  const text = `${category?.code || ''} ${category?.name || ''}`
  if (/规则|报名|赛题|guide|rule|problem/.test(text)) return 'calendar'
  if (/工具|代码|数据|tool|code|data/.test(text)) return 'spark'
  if (/官网|原文|source/.test(text)) return 'link'
  return 'book'
}

export function paginatedLibrary(data) {
  if (!Array.isArray(data?.results) || !Number.isSafeInteger(data.count) || data.count < 0) {
    throw new Error('Invalid library response')
  }
  return data
}
