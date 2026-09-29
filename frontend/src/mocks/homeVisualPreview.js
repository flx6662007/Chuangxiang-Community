// 首页视觉评审专用占位内容。只在 ?ui_preview=1 时使用，不代表真实赛事或招募。
// 删除首页的预览分支和本文件即可移除，真实 API 请求不依赖这里的数据。
export const previewCompetitions = [
  {
    id: 'preview-competition-1',
    title: '全国大学生智能系统创新挑战（示例）',
    category: { name: '人工智能' },
    level: 'national',
    edition: '2026 · 秋季',
    registration_deadline: '2026-10-11',
    previewBadge: '12 DAYS LEFT · 视觉示例',
    previewDate: '报名截止 · 10.11（示意）',
  },
  {
    id: 'preview-competition-2',
    title: '城市未来与可持续设计竞赛（示例）',
    category: { name: '城市设计' },
    level: 'national',
    edition: '2026 · 第 4 届',
    registration_deadline: '2026-10-20',
    previewBadge: 'NEW · 视觉示例',
    previewDate: '报名截止 · 10.20（示意）',
  },
  {
    id: 'preview-competition-3',
    title: '青年科研创意实践计划（示例）',
    category: { name: '科研创新' },
    level: 'university',
    edition: '2026 · 校园单元',
    submission_deadline: '2026-11-02',
    previewBadge: '视觉示例',
    previewDate: '作品提交截止 · 11.02（示意）',
  },
  {
    id: 'preview-competition-4',
    title: '绿色科技跨学科创新赛（示例）',
    category: { name: '交叉学科' },
    level: 'provincial',
    edition: '2026 · 秋季',
    registration_deadline: '2026-10-29',
    previewBadge: '视觉示例',
    previewDate: '报名截止 · 10.29（示意）',
  },
]

export const previewRecruitments = [
  {
    id: 'preview-team-1',
    code: 'DEMO-024',
    competition: { title: '智能系统创新挑战 · AI 医疗（示例）', edition: '2026 · 秋季' },
    current_skills: [{ code: 'ai', name: 'AI' }, { code: 'product', name: '产品设计' }],
    required_roles: [{ code: 'frontend', name: '前端开发' }, { code: 'ux', name: 'UI / UX' }],
    current_existing_member_count: 3,
    remaining_slots: 2,
    collaboration_mode: 'hybrid',
    campuses: [{ code: 'siping', name: '四平路校区' }],
  },
  {
    id: 'preview-team-2',
    code: 'DEMO-025',
    competition: { title: '绿色科技跨学科创新赛（示例）', edition: '2026 · 秋季' },
    current_skills: [{ code: 'research', name: '科研调研' }],
    required_roles: [{ code: 'data', name: '数据分析' }, { code: 'design', name: '视觉设计' }],
    current_existing_member_count: 2,
    remaining_slots: 2,
    collaboration_mode: 'online',
    campuses: [],
  },
]
