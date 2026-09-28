import { mockResources } from '../mocks/resources.js'

// 页面只依赖本模块的读取契约；将来接入 API 时替换这里的数据来源即可。
export const resourceDirections = [
  { value: '', label: '全部' },
  { value: 'competition', label: '竞赛' },
  { value: 'research', label: '科研' },
  { value: 'skill', label: '技能' },
]

export const resourceCategories = [
  { value: 'map', label: '竞赛地图', description: '认识赛事体系与探索方向', icon: 'trophy' },
  { value: 'guide', label: '报名指南', description: '梳理流程与材料核对项', icon: 'calendar' },
  { value: 'tool', label: '工具资源', description: '查找常用工具与入门文档', icon: 'spark' },
  { value: 'experience', label: '经验材料', description: '积累实践方法与复盘思路', icon: 'book' },
  { value: 'source', label: '原文链接', description: '回到公开资料的原始入口', icon: 'link' },
]

export function normalizeResourceDirection(value) {
  return resourceDirections.some((item) => item.value && item.value === value) ? value : ''
}

export function normalizeResourceCategory(value) {
  return resourceCategories.some((item) => item.value === value) ? value : ''
}

export async function listResources({ search = '', direction = '', category = '' } = {}) {
  const words = (typeof search === 'string' ? search : '')
    .trim()
    .slice(0, 200)
    .toLocaleLowerCase()
    .split(/\s+/)
    .filter(Boolean)
  const selectedDirection = normalizeResourceDirection(direction)
  const selectedCategory = normalizeResourceCategory(category)
  const results = mockResources.filter((item) => {
    if (selectedDirection && item.direction !== selectedDirection) return false
    if (selectedCategory && item.category !== selectedCategory) return false
    const searchable = [item.title, item.description, ...item.tags]
      .join(' ')
      .toLocaleLowerCase()
    return words.every((word) => searchable.includes(word))
  })
  return { results, count: results.length }
}

export async function getResource(id) {
  return mockResources.find((item) => item.id === id) || null
}
