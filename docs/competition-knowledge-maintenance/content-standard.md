# 赛事成品标准与字段字典

## 正文模板

赛事名称、明确届次 → 赛事简介 → 参赛对象 → 赛道与作品要求 → 组队要求 → 报名方式 → 重要时间 → 学习资料 → 官方来源。

缺少可靠内容的章节省略，不填充免责声明。正文中的事实句说明具体对象、动作、人数、日期或限制；原文位置、适用届次和核验日期保存在证据对象中。标题中的目录年份与资料届次冲突时使用赛事系列名，届次单列。

| 原文问题 | 成品处理 |
| --- | --- |
| “已核验 2026 年第八届” | “2026 年第八届” |
| “字段映射待审核” | 移入内部处理记录 |
| “学校截止日期不适用于外校” | 整段校内安排移入内部记录，避免留下错误的全国截止日期 |
| “报名时间不明，请以后续通知为准” | 不展示报名日期；内部记录缺口 |
| 真实规则“不得跨校组队” | 保留，并关联规则来源 |
| 官方赛事名称、主办方含学校名 | 保留真实名称，不以删除学校名改变赛事身份 |

“报名时间尚未公布”需要官方明确表述；未找到日期只能记为信息不足。不同赛道的人数与日期分别解释，不能拼接成共同规则。

学习资料描述其知识内容与具体练习用途。赛事要求与通用教程分别保存；工具教程不能作为赛事允许使用某工具的依据。

## 数据层次

系列用 `catalog_code` / `catalog_codes` 关联原目录；同一实际赛事届次可以关联多个目录项目。`id` / `code` 是稳定的届次或概览记录标识；`edition` 保存官方届次与赛季。独立赛道使用独立记录或带清晰适用范围的正文，未统一的赛道规则不写入全赛事共同字段。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `title`、`edition`、`summary` | string | 面向用户的名称、届次、简介 |
| `kind` | `overview` / `edition` | 系列知识或具体届次 |
| `aliases` | string[] | 真实简称、别名与旧称 |
| `category` | string | 沿用类别字典的学科分类，不表示资格限制 |
| `level` | string | 沿用赛事范围；未知用 `unknown` |
| `competition_id` | integer / null | 真实业务对象标识；纯知识记录为空 |
| `fields.eligibility` | string | 保留邀请制、院校推荐等完整对象条件 |
| `fields.education` | string[] | 本科、研究生、硕士、博士、专科的规范值 |
| `fields.grades`、`fields.majors` | string[] | 明确公布的年级、专业范围；空缺不表示不限 |
| `fields.participation_type` | `individual` / `team` / `both` | 明确公布的参赛形式 |
| `fields.team_size_min/max` | integer | 共同规则的人数上下界 |
| `fields.registration_start/deadline` | ISO date | 报名窗口 |
| `fields.submission_deadline` | ISO date | 作品截止，独立于报名截止 |
| `fields.registration_url/method` | string | 官方入口与报名步骤 |
| `field_evidence` | object | 每个字段对应的 source id 列表 |
| `sections` | object[] | 稳定章节 id、标题、正文与 evidence_ids |
| `sources` | object[] | source id、URL、标题、原文位置 locator、verified_at、quote |
| `content_hash` | SHA-256 | 当前记录内容的确定性哈希 |
| `version` | string | 整体语料内容版本 |

`quote` 只保存逐字核对的原文，不用整理摘要填充。来源位置至少给出章节、条款或页面段落；PDF 优先保留页码。日期与人数等匹配字段必须有字段级来源关联。

## 质量检查

执行 `python scripts/check-competition-knowledge.py` 检查 255 项处理结论、20 项样本、三批覆盖、来源关联、正文过程语言、段落一致性和内容哈希；执行产品转换与检索单元测试，检查真实禁止条款仍保留。

词表检查只负责发现可疑句子，人工复核决定事实是否完整、适用范围是否正确。公开正文、标题、届次、学习资料简介与模型片段全部检查；原目录背景、路径、署名和校内安排只出现在维护材料中。

`processing-report.json` 保存每项目录的正式收录或内部处理结论及原因。`source-access-report.json` 只记录地址访问情况；成功获取页面不等于已核实全部规则。`verified-supplements.json` 保存逐条核对后的补充事实，重建时与原始底稿合并。
