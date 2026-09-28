// 仅供首页 AI 竞赛助手演示：以下赛事均为虚构数据，不代表平台已发布的赛事。
function dateAfter(days) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const category = (id, code, name) => ({ id, code, name })
const tag = (id, code, name) => ({ id, code, name })

function competition(details) {
  return {
    code: `mock-ai-${Math.abs(details.id)}`,
    edition: '演示届次',
    level: 'unknown',
    organizer: '本地 Mock 演示',
    registration_deadline: null,
    registration_deadline_at: null,
    registration_deadline_timezone: '',
    submission_deadline: null,
    submission_deadline_at: null,
    submission_deadline_timezone: '',
    published_at: null,
    updated_at: null,
    last_verified_at: null,
    is_recruitment_open: false,
    primary_source: null,
    deadline_status: 'unknown',
    deadline_kind: 'unknown',
    deadline_status_label: '演示数据：截止时间未明确',
    ...details,
  }
}

const openRegistration = (days) => ({
  registration_deadline: dateAfter(days),
  deadline_status: 'open',
  deadline_kind: 'registration',
  deadline_status_label: '演示数据：报名截止日期尚未到',
})

export const mockAICompetitions = [
  competition({
    id: -101,
    title: '【演示】智能科学跨学科挑战赛',
    summary: '围绕物理实验数据与机器学习方法设计作品。本条仅用于前端交互演示。',
    category: category(1, 'science', '科学创新'),
    tags: [tag(1, 'ai', '人工智能'), tag(2, 'physics', '物理')],
    participation_type: 'team',
    eligibility: '物理及相关专业，大二及以上，可组队参加（演示条件）',
    ...openRegistration(18),
  }),
  competition({
    id: -102,
    title: '【演示】人工智能应用创意赛',
    summary: '用人工智能工具探索校园应用场景。本条仅用于前端交互演示。',
    category: category(2, 'innovation', '创新实践'),
    tags: [tag(1, 'ai', '人工智能'), tag(3, 'creative', '创意实践')],
    participation_type: 'both',
    eligibility: '全专业大二及以上，可个人或组队参加（演示条件）',
    ...openRegistration(27),
  }),
  competition({
    id: -103,
    title: '【演示】本科生科研创新项目赛',
    summary: '以研究问题、实验方案和创新成果为主题。本条仅用于前端交互演示。',
    category: category(1, 'science', '科学创新'),
    tags: [tag(4, 'research', '科研创新')],
    participation_type: 'team',
    eligibility: '本科生大二及以上，可组队参加（演示条件）',
    ...openRegistration(12),
  }),
  competition({
    id: -104,
    title: '【演示】机器人系统设计赛',
    summary: '围绕机器人结构与控制方案展开设计。本条仅用于前端交互演示。',
    category: category(3, 'engineering', '工程技术'),
    tags: [tag(5, 'robotics', '机器人'), tag(6, 'design', '设计')],
    participation_type: 'team',
    eligibility: '全专业在校本科生，可组队参加（演示条件）',
  }),
  competition({
    id: -105,
    title: '【演示】创意设计实践赛',
    summary: '从日常问题出发完成设计提案。本条仅用于前端交互演示。',
    category: category(2, 'innovation', '创新实践'),
    tags: [tag(6, 'design', '设计'), tag(3, 'creative', '创意实践')],
    participation_type: 'individual',
    eligibility: '全专业大二及以上，个人参加（演示条件）',
    ...openRegistration(21),
  }),
  competition({
    id: -106,
    title: '【演示】物理实验研究成果赛',
    summary: '展示物理实验和科研探索的阶段性成果。本条仅用于前端交互演示。',
    category: category(1, 'science', '科学创新'),
    tags: [tag(2, 'physics', '物理'), tag(4, 'research', '科研创新')],
    participation_type: 'both',
    eligibility: '物理及相关专业，大二及以上，可个人或组队参加（演示条件）',
  }),
]

const interestRules = [
  { name: '人工智能', query: /人工智能|\bai\b|机器学习|深度学习/i, item: /人工智能|\bai\b|机器学习|深度学习/i },
  { name: '科研创新', query: /科研|研究|创新/, item: /科研|研究|创新成果/ },
  { name: '机器人', query: /机器人|智能制造/, item: /机器人|智能制造/ },
  { name: '设计创意', query: /设计|创意/, item: /设计|创意/ },
]

export function interpretMockQuery(query) {
  const text = query.trim()
  const gradeMatch = text.match(/大[一二三四]|[一二三四]年级/)
  const grade = gradeMatch?.[0]?.endsWith('年级')
    ? `大${gradeMatch[0][0]}`
    : gradeMatch?.[0] || null
  return {
    major: /物理/.test(text) ? '物理' : /计算机/.test(text) ? '计算机' : null,
    grade,
    interests: interestRules.filter((rule) => rule.query.test(text)).map((rule) => rule.name),
    participationType: /组队|团队|队友/.test(text)
      ? 'team'
      : /个人|独立参赛/.test(text) ? 'individual' : null,
    registrationStatus: /近期|可报名|还能报名|报名|未截止/.test(text) ? 'open' : null,
  }
}

function searchableText(item) {
  return [item.title, item.summary, item.category?.name, item.eligibility, ...item.tags.map((tag) => tag.name)].join(' ')
}

// 规则匹配只用于模拟交互，理由只能引用本地演示字段，不能当作资格判断。
export function mockAICompetitionSearch(query) {
  const interpretation = interpretMockQuery(query)
  const hasIntent = interpretation.major || interpretation.grade ||
    interpretation.interests.length || interpretation.participationType ||
    interpretation.registrationStatus
  if (!hasIntent) return { interpretation, results: [] }

  const teamPreferred = /最好|优先|希望/.test(query)
  const results = mockAICompetitions.flatMap((item) => {
    const text = searchableText(item)
    const reasons = []
    let score = 0

    if (interpretation.interests.length) {
      const matched = interpretation.interests.filter((name) =>
        interestRules.find((rule) => rule.name === name).item.test(text))
      if (!matched.length) return []
      reasons.push(`演示资料涉及${matched.join('、')}`)
      score += matched.length * 5
    }
    if (interpretation.major) {
      if (!item.eligibility.includes(interpretation.major) && !item.eligibility.includes('全专业')) return []
      reasons.push(`演示资格说明覆盖${interpretation.major}专业`)
      score += 3
    }
    if (interpretation.grade) {
      if (!item.eligibility.includes(interpretation.grade) && !item.eligibility.includes('全专业在校本科生')) return []
      reasons.push(`演示资格说明覆盖${interpretation.grade}`)
      score += 2
    }
    if (interpretation.registrationStatus === 'open') {
      if (item.deadline_status !== 'open' || item.deadline_kind !== 'registration') return []
      reasons.push('模拟报名截止日期尚未到')
      score += 2
    }
    if (interpretation.participationType) {
      const available = item.participation_type === 'both' ||
        item.participation_type === interpretation.participationType
      if (!available && (!teamPreferred || !reasons.length)) return []
      if (available) {
        reasons.push(interpretation.participationType === 'team' ? '演示参赛形式支持组队' : '演示参赛形式支持个人参加')
        score += 2
      }
    }
    return [{ competition: item, matchReason: `${reasons.join('；')}。`, score }]
  })

  results.sort((a, b) => b.score - a.score || Math.abs(a.competition.id) - Math.abs(b.competition.id))
  return {
    interpretation,
    results: results.map(({ competition, matchReason }) => ({ competition, matchReason })),
  }
}
