# 赛事字段表

版本：v1.0，2026-09-24。赛事部分已获用户审核通过，本表作为当前分支的建模交付基线。赛事、来源、分类标签模型及基础约束已编写，本地初始迁移和 PostgreSQL 建表验证已完成；发布事务、Admin 和接口待后端接入。完整规则及实现边界见 [赛事字段说明](database-fields.md#competitions)。

一条 `Competition` 记录代表一个具体赛事届次。首版不单独建立赛事系列或赛道表；不同赛道的差异写入详情，不能拆成多个赛事绕过“同届只能正式加入一个队伍”的限制。

## 一 赛事主表

模型 `competitions.Competition`，表名 `competitions_competition`。下列为实际列；标签多对多关系另列。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认值或填写方式 | 主要约束 |
| --- | --- | --- | --- | --- | --- |
| `id` | 赛事届次主键 | `BigAutoField` | 否 | 自动生成 | 主键；后续队伍、收藏引用此值 |
| `code` | 稳定业务编码 | `SlugField(80)` | 否 | 管理员或导入脚本指定 | 非空、唯一；只用小写英文字母、数字、短横线；建立后不随标题变化 |
| `title` | 含届次的展示名称 | `CharField(200)` | 否 | 创建必填 | 去首尾空格后非空；不要求唯一 |
| `edition` | 年度或届次 | `CharField(80)` | 否 | 创建必填 | 如 `2026 年度`、`第十二届`；须能确定实际届次，不凭抓取年份推断 |
| `summary` | 列表简介 | `CharField(500)` | 否 | `''` | 发布前必填；整理自来源，不存 HTML |
| `description` | 整理后的赛事详情 | `TextField` | 否 | `''` | 发布前必填；纯文本，最多 20,000 字符；不混入学生招募文案 |
| `category` | 主分类 | `ForeignKey(CompetitionTaxonomy)` | 是 | NULL | 发布前必选有效的 `category` 类型词条；`on_delete=PROTECT` |
| `level` | 来源标注的赛事范围 | `CharField(20)` | 否 | `unknown` | 选项见下文；不表示学校认定级别或获奖等级 |
| `organizer` | 主办方 | `CharField(500)` | 否 | `''` | 来源未注明可空字符串；多个主办方按来源整理 |
| `tracks` | 赛道及差异说明 | `TextField` | 否 | `''` | 最多 5,000 字符；差异较大时主表只填各赛道一致的信息 |
| `eligibility` | 官方参赛资格 | `TextField` | 否 | `''` | 最多 5,000 字符；未披露时留空，不等于所有人可参加 |
| `participation_type` | 官方参赛形式 | `CharField(20)` | 否 | `unknown` | `unknown`、`individual`、`team`、`both` |
| `team_size_min` | 官方团队人数下限 | `PositiveSmallIntegerField` | 是 | NULL | 有值时至少 1；个人赛留空；不同赛道不统一时不强填 |
| `team_size_max` | 官方团队人数上限 | `PositiveSmallIntegerField` | 是 | NULL | 有值时至少 1；与下限都有值时不得小于下限 |
| `registration_method` | 官方报名方式 | `TextField` | 否 | `''` | 最多 5,000 字符；可描述官网、校内选拔等方式，未知不补造 |
| `registration_url` | 官方报名入口 | `URLField(2048)` | 否 | `''` | 可空字符串；仅 HTTP/HTTPS；不是平台招募入口 |
| `campus_arrangements` | 同济校内安排 | `TextField` | 否 | `''` | 最多 5,000 字符；标明适用院系、赛道或选拔范围，并关联补充来源 |
| `registration_deadline` | 官方报名截止日期 | `DateField` | 是 | NULL | 未知留空；只存来源明确的完整日期 |
| `registration_deadline_at` | 官方报名精确截止时刻 | `DateTimeField` | 是 | NULL | 仅来源明确日期、时刻、时区时填写；与对应日期一致 |
| `registration_deadline_timezone` | 官方报名截止的来源时区 | `CharField(64)` | 否 | `''` | 时区未知留空；精确时刻有值时必填 |
| `submission_deadline` | 作品提交截止日期 | `DateField` | 是 | NULL | 不与报名截止混用；不同赛道不一致时留空并说明 |
| `submission_deadline_at` | 作品提交精确截止时刻 | `DateTimeField` | 是 | NULL | 精确时刻有值时，日期和对应时区必须有值 |
| `submission_deadline_timezone` | 作品提交截止的来源时区 | `CharField(64)` | 否 | `''` | 与报名时区采用相同格式，但独立保存 |
| `campus_deadline` | 同济校内报名或选拔截止日期 | `DateField` | 是 | NULL | 具体事项和适用范围写入校内安排，不替代官方截止日期 |
| `campus_deadline_at` | 校内截止的精确时刻 | `DateTimeField` | 是 | NULL | 精确时刻有值时，日期和对应时区必须有值 |
| `campus_deadline_timezone` | 校内截止的来源时区 | `CharField(64)` | 否 | `''` | 确认采用北京时间时填写 `Asia/Shanghai` |
| `deadline_notes` | 时间适用范围及例外 | `TextField` | 否 | `''` | 最多 5,000 字符；说明延期、分批、不同赛道或时间待通知 |
| `publication_status` | 平台发布状态 | `CharField(20)` | 否 | `draft` | `draft`、`published`、`withdrawn`；公开接口只返回 `published` |
| `published_at` | 平台首次发布时间 | `DateTimeField` | 是 | NULL | 第一次发布时由系统填写，后续编辑或重新上架不重置 |
| `withdrawal_reason` | 最近一次下架原因 | `CharField(500)` | 否 | `''` | 下架时必填；内部字段，不公开 |
| `last_verified_at` | 最近整条信息核验时间 | `DateTimeField` | 是 | NULL | 发布前必填；由管理员确认或后续核验流程更新，单纯抓取不更新 |
| `created_at` | 平台建档时间 | `DateTimeField` | 否 | `auto_now_add` | 系统维护，不代表原通知发布时间 |
| `updated_at` | 平台内容更新时间 | `DateTimeField` | 否 | `auto_now` | 来源、标签或可见内容变化时也更新；导入无变化时不刷新 |
| `created_by` | 建档操作者 | `ForeignKey(User)` | 是 | NULL | 指向 `settings.AUTH_USER_MODEL`；`on_delete=SET_NULL`；自动任务可空 |
| `updated_by` | 最近内容修改操作者 | `ForeignKey(User)` | 是 | NULL | 同上；系统任务更新时为空，不沿用上次操作者冒充本次操作者 |
| `recruitment_enabled` | 是否开放本届站内组队招募 | `BooleanField` | 否 | False | 管理员维护；启用前核对团队参赛条件和允许组队期限 |
| `recruitment_deadline` | 本届平台招募截止时刻 | `DateTimeField` | 是 | NULL | 开放招募时必填；带时区，不从未知或仅日期信息中推算精确时刻 |
| `recruitment_note` | 平台招募期限依据 | `CharField(1000)` | 否 | `''` | 启用招募时必填；内部记录核验依据及适用范围 |

| 多对多关系 | 类型 | 初始值 | 约束 |
| --- | --- | --- | --- |
| `tags` | `ManyToManyField(CompetitionTaxonomy)` | 空关系 | 只可关联 `tag` 类型词条；新增关系只能选启用词条；同一赛事与同一标签不重复 |

分类、标签使用下文词条表；首版不预设没有来源依据的标签。普通用户只能筛选，内容管理员从受控词条中选择，词条管理员维护词库。

## 二 赛事来源表

模型 `competitions.CompetitionSource`，表名 `competitions_competitionsource`。一届赛事可有多个来源；主来源可以是赛事官方通知或正式校内通知，其他链接用于补充和更正。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认值或填写方式 | 主要约束 |
| --- | --- | --- | --- | --- | --- |
| `id` | 来源主键 | `BigAutoField` | 否 | 自动生成 | 主键 |
| `competition` | 所属赛事届次 | `ForeignKey(Competition)` | 否 | 必填 | `on_delete=CASCADE`；一条来源记录只属于一个届次 |
| `source_type` | 来源类型 | `CharField(20)` | 否 | 必填，无默认值 | `official` 赛事官方、`campus` 校内官方 |
| `source_name` | 来源名称 | `CharField(200)` | 否 | 必填 | 发布机构或网站名称，去首尾空格后非空 |
| `source_url` | 原文链接 | `URLField(2048)` | 否 | 必填 | HTTP/HTTPS；非全局唯一，同一通知可涉及不同赛事届次 |
| `is_primary` | 是否主来源 | `BooleanField` | 否 | False | 数据库保证每届至多一个主来源；发布校验要求恰好一个 |
| `source_published_on` | 原通知发布日期 | `DateField` | 是 | NULL | 首版精度为日期；未知不以抓取日期代替 |
| `source_updated_on` | 原通知更新日期 | `DateField` | 是 | NULL | 原文明确给出更新日期时填写；重新抓取不修改 |
| `fetched_at` | 最近成功采集时间 | `DateTimeField` | 是 | NULL | 采集服务成功读取时写入；手工录入可空，不表示核验通过 |
| `last_verified_at` | 此来源最近核验时间 | `DateTimeField` | 是 | NULL | 核验流程填写；用于发布的来源必须核验 |

来源附属于赛事；仅允许硬删除从未发布且没有业务引用的草稿。已发布过的赛事使用下架保留记录，不通过删除来源绕过发布校验。

## 三 分类与标签词条表

模型 `competitions.CompetitionTaxonomy`，表名 `competitions_competitiontaxonomy`。统一维护可选词条，分类和标签由 `kind` 区分；本表不承担科研项目分类。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认值或填写方式 | 主要约束 |
| --- | --- | --- | --- | --- | --- |
| `id` | 词条主键 | `BigAutoField` | 否 | 自动生成 | 主键 |
| `code` | 稳定词条编码 | `SlugField(64)` | 否 | 管理员必填 | 非空、全表唯一、小写字母/数字/短横线；建立后固定 |
| `kind` | 词条用途 | `CharField(20)` | 否 | 管理员必填 | `category` 或 `tag`；建立后不更改用途 |
| `name` | 展示名称 | `CharField(50)` | 否 | 管理员必填 | 去首尾空格后非空；同一 `kind` 下名称唯一 |
| `is_active` | 是否可供新选择 | `BooleanField` | 否 | True | 停用不抹除历史关联；被引用词条不硬删除 |
| `sort_order` | 展示顺序 | `PositiveIntegerField` | 否 | 0 | 升序，相同时按主键排序 |

## 四 枚举与通用约定

| 字段 | 固定取值 |
| --- | --- |
| `publication_status` | `draft` 草稿；`published` 已公开；`withdrawn` 已下架 |
| `participation_type` | `unknown` 未说明；`individual` 个人赛；`team` 团队赛；`both` 同届同时允许个人与团队参赛 |
| `level` | `unknown` 未注明；`international` 国际；`national` 全国；`provincial` 省级；`municipal` 市级；`university` 校级；`college` 院系级；`other` 其他 |
| `source_type` | `official` 赛事官方；`campus` 校内官方 |
| `CompetitionTaxonomy.kind` | `category` 主分类；`tag` 标签 |

- `CharField(n)` 等写法表示 `max_length=n`，不是可直接复制的构造代码。可选字符串使用 `''`，可选日期、时间、数字、外键使用 NULL；它们均允许表单留空。零不能代替未知人数。
- 必填与可空分两层：数据库允许草稿不完整；发布前执行统一校验。`summary`、`description`、有效分类、已核验主来源和整体核验时间是发布条件；截止日期未知本身不阻止发布。
- `DateTimeField` 保存带时区时刻；页面通常按 `Asia/Shanghai` 展示，并保留来源日期、时区供解释。时区允许有效 IANA 名称（如 `Asia/Shanghai`）或固定偏移（如 `+08:00`）。
- 时间字段日期为空时，对应精确时刻必须为空、时区为 `''`；精确时刻有值时，其在来源时区下的日期必须等于日期字段。只有日期时不补 `00:00` 或 `23:59:59`。
- 数据库外键列自动追加 `_id`；标签关联由 Django 建立中间表。赛事标题、届次文本、原文 URL 均不单独唯一；`code` 唯一也不代替导入前的同届核对。
- 报名已截止的赛事仍可保持公开历史。截止状态、日期精度、是否允许当前用户发布招募等为计算结果，不重复保存布尔状态列。

## 五 交付边界

本次确定赛事、来源、分类标签及关联说明。队伍 `Team`、招募卡 `Recruitment`、申请和成员关系另表交付；主表只保留本届是否允许招募及期限。科研项目仍待继续细化，不视为本次一起定稿；讨论大纲不随本轮代码交付。

初始迁移和虚构样例已完成本机 PostgreSQL 验证，复现步骤见 [数据库初始化与验收](database-handoff.md#initialization)。下一步按交接流程提交本轮改动，与用户及赛事模型一起供后端统一审核；发布事务、Admin 和接口按后续阶段实现。
