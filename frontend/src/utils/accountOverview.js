export function accountOverview(profile) {
  if (!profile) return null

  const eligibility = profile.account_eligibility
  const reasons = Array.isArray(eligibility?.reasons) ? eligibility.reasons : []
  if (reasons.includes('account_disabled') || reasons.includes('account_restricted')) {
    return {
      status: reasons.includes('account_disabled') ? '账号已停用' : '账号受限',
      title: '查看账号限制说明',
      description: '查看当前限制与可申诉事项，再决定下一步。',
      to: { name: 'account', hash: '#account-status' },
    }
  }
  if (reasons.includes('email_unverified') || profile.school_email_verified === false) {
    return {
      status: '邮箱待核验',
      title: '验证学校邮箱',
      description: '收取学校邮箱中的验证码，完成身份核验。',
      to: { name: 'account', hash: '#email-verification' },
    }
  }
  if (reasons.includes('contact_required') || profile.has_contact_details === false) {
    return {
      status: '联系方式待补充',
      title: '补充联系方式',
      description: '至少填写微信号或手机号，方便后续组队联系。',
      to: { name: 'account', hash: '#contact-details' },
    }
  }
  if (eligibility?.eligible === true) {
    return {
      status: '具备基础资格',
      title: '浏览团队广场',
      description: '可以寻找合适的招募；发布和申请仍受赛事、队伍及名额条件限制。',
      to: { name: 'teams' },
    }
  }
  return {
    status: '状态待核实',
    title: '查看账号状态',
    description: '请刷新状态，确认目前的发布与申请条件。',
    to: { name: 'account', hash: '#account-status' },
  }
}
