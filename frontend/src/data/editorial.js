// 手动维护的编辑内容；无记录时显示空态，不生成虚构资讯。
// 通用字段：id、title、date（原文日期，未注明用空串）、summary、sourceUrl。
// 实验室可补：unit、participation、evidenceNote、verifiedOn。
export const newsletters = []
export const laboratories = [
  {
    id: 'tongji-li-bing', title: '李冰课题组 · 网联智能与无人系统',
    unit: '计算机科学与技术学院', date: '', verifiedOn: '2026-09-26',
    summary: '研究低空智联网、多智能体与网联具身智能，要求有科研时间、数理及英语基础。',
    participation: '长期招募校内外本科生',
    evidenceNote: '学院教师主页明确招募本科生；具体课题和名额需联系确认。',
    sourceUrl: 'https://cs.tongji.edu.cn/info/1066/3670.htm',
  },
  {
    id: 'tongji-jiang-shuo', title: '蒋烁课题组 · 智能机器人与多模感知',
    unit: '智能机器人与计算感知实验室', date: '', verifiedOn: '2026-09-26',
    summary: '研究具身智能、多模感知和人机系统，可按官方教师页面咨询本科科研实习。',
    participation: '明确招收本科实习生',
    evidenceNote: '官网说明每年招收本科实习生，未公布本期名额和截止日。',
    sourceUrl: 'https://robot.tongji.edu.cn/info/1256/2090.htm',
  },
  {
    id: 'tongji-meng-xiangzhou', title: '孟祥周课题组 · 环境新污染物',
    unit: '环境科学与工程学院', date: '', verifiedOn: '2026-09-26',
    summary: '研究新污染物源谱、智慧溯源与风险管控，学院主页明确欢迎本科生加入。',
    participation: '明确欢迎本科生加盟',
    evidenceNote: '教师主页招募线索；参与条件、时间和题目需向课题组确认。',
    sourceUrl: 'https://sese.tongji.edu.cn/szdw/zyjs/js/M/mxz.htm',
  },
  {
    id: 'tongji-evs', title: '干细胞外囊泡研究课题组',
    unit: '医学院', date: '2025-09-08', verifiedOn: '2026-09-26',
    summary: '研究细胞外囊泡与消化系统疾病、糖尿病。招聘公告另有明确的本科生实习说明。',
    participation: '欢迎本科生实习',
    evidenceNote: '原公告注明长期有效；技术员岗位待遇不等同于本科实习待遇。',
    sourceUrl: 'https://med.tongji.edu.cn/info/1327/13605.htm',
  },
  {
    id: 'tongji-nanophononics', title: '中欧纳米声子学联合实验室',
    unit: '物理科学与工程学院', date: '2023-05-12', verifiedOn: '2026-09-26',
    summary: '官网“本科生进实验室”栏目邀请有物理科研兴趣的同济本科生提前进组。',
    participation: '本科生进实验室',
    evidenceNote: '2023 年历史招募说明仍可访问，当前接收安排需重新确认。',
    sourceUrl: 'https://nanophononics.tongji.edu.cn/notice/qs',
  },
  {
    id: 'tongji-ipoe', title: '精密光学工程技术研究所',
    unit: '精密光学工程技术研究所', date: '2022-06-27', verifiedOn: '2026-09-26',
    summary: '设本科生科研培养说明，包含校内课题实践及校外短期访问、暑期实践等方式。',
    participation: '明确提供本科生科研培养',
    evidenceNote: '2022 年培养说明；具体方向与当前名额须联系相应教师确认。',
    sourceUrl: 'https://ipoe.tongji.edu.cn/info/1036/1020.htm',
  },
]
