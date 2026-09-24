# 业务模块字段表

版本：v1.0；2026-09-25。业务口径已经本轮逐模块确认；本表已落实为模型与迁移，并完成本机建表验证。类型、长度及拆表属于实现选择，后端可在不改变业务规则的前提下评审。配套见[字段说明](database-fields.md#teams)与[数据库交付说明](database-handoff.md)。

## 一 共用约定

- 本表共 32 张主体/历史记录表及 12 张显式多选关联表；`UserRestriction` 沿用原用户字段表，其他已完成的 User 与 Competition 表不重复建模。
- “数据库可空”指 SQL NULL；文本选填采用空串，JSON 使用独立的 dict/list。系统字段由服务维护，不要求学生或管理员逐项手填。草稿可缺发布资料，发布时才执行条件必填。
- 主键为 BigAutoField；有稳定编码的业务对象使用小写前缀加 UUID4 hex。时间存带时区的时刻；来源只有日期时只存 DateField，不补造具体时间。
- 除 J01–J12 的拥有方外键使用 CASCADE，本文外键均使用 PROTECT（含可空外键），防止删除仍被引用的历史。CASCADE 不意味着业务可任意删除版本；历史删除仍受服务权限控制。已有 User/Competition 的原删除策略保持原定义。
- 外键默认有数据库索引。枚举、同一行数据配对与条件唯一落在数据库；跨表一致性用模型 full_clean 校验，涉及人数、并发、状态变更、收件人范围的规则由事务服务完成。字段约束不等于整个 HTTP 功能已上线。

## 二 主体与历史表

### T01 teams.RecruitmentOption

表名：`teams_recruitmentoption`。角色、技能或校区的受控词条。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `code` | 稳定编码 | `SlugField(64)` | 否 | 管理员指定 | 唯一；小写字母/数字/短横线；建立后固定 |
| `kind` | 用途 | `CharField(12)` | 否 | 必填 | role / skill / campus；建立后固定；允许值：`role`、`skill`、`campus` |
| `name` | 名称 | `CharField(80)` | 否 | 必填 | 非空；同用途下唯一 |
| `is_active` | 可供新选择 | `BooleanField` | 否 | True | 停用保留引用 |
| `sort_order` | 顺序 | `PositiveIntegerField` | 否 | 0 | 非负 |

- 唯一 code、(kind,name)；kind 固定枚举。已引用的名称/含义不直接改写，纠正或调整用新词条并停用旧词条，防止历史版本变义。

索引：(kind,is_active,sort_order)。

### T02 teams.Team

表名：`teams_team`。同一具体赛事届次下持续存在的队伍；换卡不换队伍。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `code` | 稳定队伍编号 | `SlugField(80)` | 否 | team-<UUID4 hex> | 唯一；不由用户填写 |
| `competition` | 所属赛事届次 | `ForeignKey(competitions.Competition)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `recruiter` | 招募者 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `created_at` | 创建时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `dissolved_at` | 实际解散时间 | `DateTimeField` | 是 | NULL | 由完成的解散请求写入；非空后不恢复 |

- competition、recruiter 创建后不可变；活跃队伍必须有招募者的有效 Membership，创建队伍和该关系在同一事务完成。
- 队伍状态由 dissolved_at 和待处理 DissolutionRequest 计算，不重复保存 status。

索引：(competition,dissolved_at)；(recruiter,created_at)。

### T03 teams.Recruitment

表名：`teams_recruitment`。一轮招募的身份、期限与生命周期；可编辑内容放入不可变版本。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `code` | 卡片编号 | `SlugField(80)` | 否 | recruitment-<UUID4 hex> | 唯一 |
| `team` | 所属队伍 | `ForeignKey(teams.Team)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `current_revision` | 当前内容版本 | `ForeignKey(teams.RecruitmentRevision)` | 是 | NULL | on_delete=PROTECT；只允许内部原子建卡过程中为空；公开卡必须有版本且属于本卡 |
| `publication_status` | 可见状态 | `CharField(12)` | 否 | draft | draft / published / withdrawn；不把满员存为关闭；允许值：`draft`、`published`、`withdrawn` |
| `duration_days` | 选择的有效天数 | `PositiveSmallIntegerField` | 否 | 发布必选 | 仅 3 / 7 / 14；发布后固定 |
| `created_at` | 建档时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `published_at` | 首次发布时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `expires_at` | 本卡到期时刻 | `DateTimeField` | 是 | NULL | 发布必有；min(发布时间+所选天数,发布时赛事招募截止) |
| `last_edited_at` | 最后实际编辑时间 | `DateTimeField` | 是 | NULL | 首次发布为 NULL；有效内容修改才更新 |
| `closed_at` | 招募结束时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `close_reason` | 结束原因 | `CharField(32)` | 否 | '' | manual / expired / competition_stopped / competition_withdrawn / team_dissolved；未关闭为 ''；允许值：`空串`、`manual`、`expired`、`competition_stopped`、`competition_withdrawn`、`team_dissolved` |
| `closed_by` | 关闭操作者 | `ForeignKey(accounts.User)` | 是 | NULL | on_delete=PROTECT；系统结束时为空 |
| `withdrawn_at` | 最近下架时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `withdrawal_reason` | 下架原因 | `CharField(500)` | 否 | '' | 内部；withdrawn 时必有；撤销下架留存 AdminAction |

- 条件唯一 (team)，条件为 publication_status=published 且 closed_at IS NULL；包括满员和解散处理中卡。
- 发布须 current_revision、published_at、expires_at 有值；expires_at>published_at；closed_at 与 close_reason 成对。
- 时间流逝不能靠静态唯一索引自动释放卡位；发新卡前在事务中结束已到期旧卡。恢复下架不能清除原主动关闭或到期事实。

索引：(team,created_at)；(publication_status,closed_at,expires_at)。

### T04 teams.RecruitmentRevision

表名：`teams_recruitmentrevision`。某张卡的一次完整内容版本；版本创建后不可修改。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `recruitment` | 所属卡片 | `ForeignKey(teams.Recruitment)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `version` | 版本序号 | `PositiveIntegerField` | 否 | 从 1 递增 | 同卡唯一 |
| `existing_member_count` | 申报已有成员数 | `PositiveIntegerField` | 否 | 招募者填写 | 至少 1，含招募者；不含本卡当前新招到的成员 |
| `recruitment_quota` | 本轮计划招募人数 | `PositiveIntegerField` | 否 | 招募者填写 | 首次发布至少 1；编辑可为 0，但不得小于本卡当前成功人数 |
| `foundation_requirement` | 基础要求 | `CharField(24)` | 否 | 必填 | beginner_ok / introductory / project_experience；允许值：`beginner_ok`、`introductory`、`project_experience` |
| `weekly_effort` | 每周投入档位 | `CharField(16)` | 否 | 必填 | up_to_2 / over_2_to_5 / over_5_to_10 / over_10；允许值：`up_to_2`、`over_2_to_5`、`over_5_to_10`、`over_10` |
| `collaboration_goal` | 合作目标 | `CharField(24)` | 否 | '' | '' / learning / deliver_entry / strong_result；允许值：`空串`、`learning`、`deliver_entry`、`strong_result` |
| `expected_duration` | 入队后合作时长 | `CharField(24)` | 否 | '' | '' / up_to_1_month / over_1_to_3_months / over_3_to_6_months / over_6_months；允许值：`空串`、`up_to_1_month`、`over_1_to_3_months`、`over_3_to_6_months`、`over_6_months` |
| `collaboration_mode` | 协作方式 | `CharField(12)` | 否 | 必填 | online / offline / hybrid；允许值：`online`、`offline`、`hybrid` |
| `edited_by` | 本次编辑人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `created_at` | 本版本生效时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |

- 唯一 (recruitment,version)；所有枚举由数据库 CheckConstraint 限定。
- 角色、能力、技能和校区见关系表 J01–J04；非线上模式至少选一个校区，线上校区为空。
- 名额、官方人数上限、基数成员一致性和版本递增须事务校验；不可直接改旧版本。

索引：(recruitment,version) 唯一索引。

### T05 teams.RecruitmentBaselineMember

表名：`teams_recruitmentbaselinemember`。本版本申报已有成员数中，已被平台识别的正式成员；线下成员不逐人建档。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `revision` | 人数申报版本 | `ForeignKey(teams.RecruitmentRevision)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `membership` | 计入基数的成员关系 | `ForeignKey(teams.Membership)` | 否 | 写入服务指定 | on_delete=PROTECT； |

- 唯一 (revision,membership)；只能是该队在版本生效时有效、且不是通过本卡加入的成员，包含招募者。
- 这些成员后来退出时，仅从该版本已有成员的实时展示数中扣除，不扩大新卡 quota；新版本重新建立当时有效成员清单。

索引：(membership,revision)。

### T06 teams.Application

表名：`teams_application`。一人对一张卡唯一的一次申请；终结后不复用。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `recruitment` | 目标卡片 | `ForeignKey(teams.Recruitment)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `applicant` | 申请人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `current_revision` | 当前申请资料版本 | `ForeignKey(teams.ApplicationRevision)` | 是 | NULL | on_delete=PROTECT；仅原子创建过程可空；提交后必有且属于本申请 |
| `status` | 处理阶段 | `CharField(20)` | 否 | pending | pending / contact_open / joined / withdrawn / rejected / ended；允许值：`pending`、`contact_open`、`joined`、`withdrawn`、`rejected`、`ended` |
| `submitted_at` | 提交时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `contact_opened_at` | 接受并开放联系方式时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `applicant_confirmed_at` | 申请人当前正式确认时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `applicant_confirmed_revision` | 申请人确认的申请版本 | `ForeignKey(teams.ApplicationRevision)` | 是 | NULL | on_delete=PROTECT； |
| `recruiter_confirmed_at` | 招募者当前正式确认时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `recruiter_confirmed_revision` | 招募者确认的申请版本 | `ForeignKey(teams.ApplicationRevision)` | 是 | NULL | on_delete=PROTECT； |
| `resolved_at` | 申请终结时间 | `DateTimeField` | 是 | NULL | joined/withdrawn/rejected/ended 时有值 |
| `end_reason` | 结束原因 | `CharField(32)` | 否 | '' | 见枚举 E4；joined 时为 ''，不把后来成员退出改写成申请失败；允许值：`空串`、`joined`、`withdrawn`、`rejected`、`recruiter_terminated`、`full`、`expired`、`card_closed`、`card_withdrawn`、`competition_stopped`、`competition_withdrawn`、`joined_other_team`、`team_dissolved`、`account_disabled` |

- 唯一 (recruitment,applicant)；各确认时间与对应版本同时有值或同时为空。
- 旧条件确认保留历史事件；继续申请生成新资料版本并清空双方当前确认。
- 因卡片内容更新、队伍解散等待而暂停是计算结果，不用一个状态覆盖原处理阶段。Membership 反向一对一关联即入队结果，不再重复存 membership_id。

索引：(applicant,status,submitted_at)；(recruitment,status)。

### T07 teams.ApplicationRevision

表名：`teams_applicationrevision`。初次提交或卡片更新后继续申请时的资料版本与条件接受记录。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `application` | 所属申请 | `ForeignKey(teams.Application)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `version` | 资料版本号 | `PositiveIntegerField` | 否 | 从 1 递增 | 同申请唯一 |
| `recruitment_revision` | 已接受的卡片版本 | `ForeignKey(teams.RecruitmentRevision)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `weekly_effort` | 每周可投入时间 | `CharField(16)` | 否 | 必填 | 与卡片相同四档；允许值：`up_to_2`、`over_2_to_5`、`over_5_to_10`、`over_10` |
| `accepted_at` | 申请人接受该版条件的时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `created_by` | 提交或继续的申请人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | on_delete=PROTECT； |

- 唯一 (application,version)；创建人与 application.applicant 一致。
- 角色、技能见 J05–J06；均选填多选，角色只能取所接受卡片版本提供的角色，技能用受控技能词库。
- 资料版本不可原地编辑；初次提交之后只有因卡片变更选择继续时可以生成下一版。

索引：(application,version) 唯一索引。

### T08 teams.Membership

表名：`teams_membership`。用户在队伍中的一段正式成员关系；结束只填结束信息，不删除。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `team` | 队伍 | `ForeignKey(teams.Team)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `competition` | 所属赛事届次 | `ForeignKey(competitions.Competition)` | 否 | 写入服务指定 | on_delete=PROTECT；受控冗余；必须等于 team.competition，用于同届唯一约束 |
| `user` | 成员账号 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `join_source` | 加入来源 | `CharField(16)` | 否 | 必填 | recruiter / application；允许值：`recruiter`、`application` |
| `application` | 成功申请 | `OneToOneField(teams.Application)` | 是 | NULL | PROTECT；recruiter 来源为空；application 来源必有 |
| `joined_at` | 正式加入时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `ended_at` | 成员关系结束时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `end_reason` | 结束方式 | `CharField(20)` | 否 | '' | '' / exit / removal / dissolution；允许值：`空串`、`exit`、`removal`、`dissolution` |

- 条件唯一 (user,competition)，条件 ended_at IS NULL；申请来源一对一，不能重复生成成员。
- join_source 与 application 是否为空匹配；ended_at 与 end_reason 成对，ended_at>=joined_at。
- 队伍/赛事/申请人/申请所属卡一致性由事务检查；外键和唯一约束不独立保证所有跨表业务条件。

索引：(team,ended_at)；(application) 一对一索引。

### T09 teams.DepartureRequest

表名：`teams_departurerequest`。成员退出与招募者移除共用请求表，保留两个业务名称。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `membership` | 目标成员关系 | `ForeignKey(teams.Membership)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `kind` | 请求类型 | `CharField(12)` | 否 | 必填 | exit / removal；允许值：`exit`、`removal` |
| `initiator` | 发起人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `responder` | 应回应人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `created_at` | 发起时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `deadline_at` | 回应截止 | `DateTimeField` | 否 | created_at + 24 小时（服务计算） | created_at+24 小时，固定 |
| `status` | 请求结果 | `CharField(24)` | 否 | pending | pending / approved / rejected / withdrawn / timed_out / team_dissolved；允许值：`pending`、`approved`、`rejected`、`withdrawn`、`timed_out`、`team_dissolved` |
| `response` | 实际回应 | `CharField(12)` | 否 | '' | '' / agree / reject；超时不伪造 agree；允许值：`空串`、`agree`、`reject` |
| `responded_at` | 实际回应时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `resolved_at` | 请求结束时间 | `DateTimeField` | 是 | NULL | 系统维护 |

- 条件唯一 (membership)，条件 status=pending；initiator!=responder；deadline_at=created_at+24h。
- exit 由成员发起、招募者回应；removal 方向相反；不适用于招募者对自己申请。
- 状态/回应/时间组合见说明；撤回和拒绝均不结束成员关系，无自由理由字段。

索引：(status,deadline_at)；(responder,status)；(membership,created_at)。

### T10 teams.DissolutionRequest

表名：`teams_dissolutionrequest`。招募者发起的一次整队解散请求。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `team` | 目标队伍 | `ForeignKey(teams.Team)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `initiator` | 发起招募者 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `created_at` | 发起时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `deadline_at` | 回应截止 | `DateTimeField` | 否 | created_at + 24 小时（服务计算） | created_at+24 小时；无其他平台成员可提前直接完成 |
| `status` | 结果 | `CharField(16)` | 否 | pending | pending / completed / rejected / withdrawn；允许值：`pending`、`completed`、`rejected`、`withdrawn` |
| `completion_reason` | 完成方式 | `CharField(24)` | 否 | '' | '' / all_agreed / timeout / no_other_members；允许值：`空串`、`all_agreed`、`timeout`、`no_other_members` |
| `resolved_at` | 请求结束时间 | `DateTimeField` | 是 | NULL | 系统维护 |

- 条件唯一 (team)，条件 status=pending；发起人必须为该队招募者。
- completed 才有 completion_reason；非 pending 必有 resolved_at。重复同意不重复解散，已结束请求不能重开。

索引：(status,deadline_at)；(team,created_at)。

### T11 teams.DissolutionResponse

表名：`teams_dissolutionresponse`。解散发起时需回应的其他平台成员；未注册成员不生成记录。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键；内部引用 |
| `request` | 解散请求 | `ForeignKey(teams.DissolutionRequest)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `membership` | 当时有效成员 | `ForeignKey(teams.Membership)` | 否 | 写入服务指定 | on_delete=PROTECT； |
| `response` | 实际回应 | `CharField(12)` | 否 | '' | '' / agree / reject；允许值：`空串`、`agree`、`reject` |
| `responded_at` | 回应时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `excluded_at` | 因个人退出不再需回应的时间 | `DateTimeField` | 是 | NULL | 仅成员先按个人流程结束且解散仍待处理时填写；不是同意票 |

- 唯一 (request,membership)；回应与回应时间成对；目标属于请求队伍且不为招募者。
- 每成员同请求只作一次实际回应；重复相同动作幂等，不支持事后改答。任何有效拒绝立即终结请求。

索引：(request,response)；(membership,request)。

### R01 research.ResearchTaxonomy

表名：`research_researchtaxonomy`。受控分类、标签及研究/适用方向，不与现有赛事词条合表。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `code` | 编码 | `SlugField(64)` | 否 | 管理员指定 | 唯一，建立后固定 |
| `kind` | 用途 | `CharField(12)` | 否 | 必填 | category / tag / direction；允许值：`category`、`tag`、`direction` |
| `name` | 名称 | `CharField(80)` | 否 | 必填 | 非空；同 kind 唯一 |
| `is_active` | 可供新选择 | `BooleanField` | 否 | True |  |
| `sort_order` | 排序 | `PositiveIntegerField` | 否 | 0 | 非负 |

- 唯一 code、(kind,name)；已引用词条不硬删除；kind 和 code 固定，历史版本冻结当时显示名称。

索引：(kind,is_active,sort_order)。

### R02 research.ResearchOpportunity

表名：`research_researchopportunity`。一次具体科研招募。人工发布必填仅为基本信息、招募主体、官方信息链接。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `code` | 稳定编号 | `SlugField(80)` | 否 | research-<UUID4 hex> | 唯一 |
| `title` | 标题 | `CharField(200)` | 否 | 必填 | 非空 |
| `description` | 基本介绍/原文说明 | `TextField` | 否 | '' | MaxLengthValidator(20000)；发布必填；允许保留非结构化文字，不要求逐项拆解 |
| `summary` | 列表短摘要 | `CharField(500)` | 否 | '' | 选填；为空时显示 description 的纯文本摘录，不依赖 AI |
| `recruiting_entity` | 招募主体原文 | `CharField(1000)` | 否 | '' | 发布必填；不强制拆分或关联账号 |
| `official_url` | 官方信息链接 | `URLField(2048)` | 否 | '' | 发布必填 HTTP/HTTPS；不必是报名提交页面 |
| `official_source_name` | 官方来源名称 | `CharField(200)` | 否 | '' |  |
| `supervisor` | 可提取的导师名称 | `CharField(200)` | 否 | '' |  |
| `research_group` | 可提取的课题组/实验室 | `CharField(200)` | 否 | '' |  |
| `institution` | 可提取的院系/机构 | `CharField(200)` | 否 | '' |  |
| `category` | 可选分类 | `ForeignKey(research.ResearchTaxonomy)` | 是 | NULL | PROTECT；kind=category；发布也允许为空 |
| `work_content` | 独立工作内容 | `TextField` | 否 | '' | MaxLengthValidator(5000)；选填；纯文本 |
| `eligibility` | 面向对象 | `TextField` | 否 | '' | MaxLengthValidator(5000)；选填；纯文本 |
| `requirements` | 能力要求 | `TextField` | 否 | '' | MaxLengthValidator(5000)；选填；纯文本 |
| `vacancies_text` | 名额原文 | `CharField(500)` | 否 | '' |  |
| `vacancies_min` | 有依据的最少名额 | `PositiveIntegerField` | 是 | NULL | 未知不填 0 |
| `vacancies_max` | 有依据的最多名额 | `PositiveIntegerField` | 是 | NULL | 双方有值 min<=max；明确招满以状态表达 |
| `weekly_hours_text` | 投入原文 | `CharField(500)` | 否 | '' |  |
| `weekly_hours_min` | 每周最低小时数 | `DecimalField(5,2)` | 是 | NULL | 0<=值<=168；仅明确数值时填 |
| `weekly_hours_max` | 每周最高小时数 | `DecimalField(5,2)` | 是 | NULL | 0<=值<=168；min<=max |
| `duration_text` | 合作周期原文 | `CharField(500)` | 否 | '' |  |
| `starts_on` | 明确开始日期 | `DateField` | 是 | NULL | 月份级别不补造具体日 |
| `ends_on` | 明确结束日期 | `DateField` | 是 | NULL | 两者有值 starts_on<=ends_on |
| `collaboration_mode` | 协作方式 | `CharField(12)` | 否 | unknown | unknown / online / offline / hybrid；允许值：`unknown`、`online`、`offline`、`hybrid` |
| `location_text` | 地点原文 | `CharField(500)` | 否 | '' |  |
| `application_instructions` | 申请说明 | `TextField` | 否 | '' | MaxLengthValidator(5000)；选填；纯文本 |
| `application_url` | 可选独立报名链接 | `URLField(2048)` | 否 | '' | 选填 HTTP/HTTPS |
| `application_email` | 可选公开申请邮箱 | `EmailField(254)` | 否 | '' | 来源公开地址，不是平台用户私有资料 |
| `deadline_mode` | 截止类型 | `CharField(12)` | 否 | unknown | unknown / fixed / ongoing；允许值：`unknown`、`fixed`、`ongoing` |
| `deadline_on` | 截止日期 | `DateField` | 是 | NULL |  |
| `deadline_at` | 精确截止时刻 | `DateTimeField` | 是 | NULL | 有值时日期与时区必有且匹配 |
| `deadline_timezone` | 来源时区 | `CharField(64)` | 否 | '' | 有效 IANA 或固定偏移；未明确不补造 |
| `deadline_notes` | 截止原文与例外 | `CharField(1000)` | 否 | '' |  |
| `closed_at` | 核实结束时间 | `DateTimeField` | 是 | NULL | 管理员确认结束；日期届满展示状态也可计算 |
| `closure_note` | 结束说明 | `CharField(500)` | 否 | '' |  |
| `last_verified_at` | 最近实际核验时间 | `DateTimeField` | 是 | NULL | 不因抓取或普通保存自动填写 |
| `verification_note` | 内部核验说明 | `TextField` | 否 | '' | MaxLengthValidator(2000)；选填；纯文本 |
| `publication_status` | 发布状态 | `CharField(12)` | 否 | draft | draft / published / withdrawn；允许值：`draft`、`published`、`withdrawn` |
| `published_at` | 首次发布时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `last_edited_at` | 最近内容编辑时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `withdrawal_reason` | 最近下架原因 | `CharField(500)` | 否 | '' | 下架时必有；内部；历史另存 AdminAction |
| `content_version` | 当前内容版本号 | `PositiveIntegerField` | 否 | 1 | 实际内容/关系变化递增；同事务产生完整快照 |
| `created_at` | 建档时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `updated_at` | 最近维护时间 | `DateTimeField` | 否 | timezone.now | auto_now；不作为原通知时间 |
| `created_by` | 创建人 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT；自动任务可空 |
| `updated_by` | 最近操作者 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT；自动任务本次为空，不冒用上次人员 |

- 发布只额外检查 title、description、recruiting_entity、official_url；category、申请详情和核验材料不是人工必填门槛。
- 枚举及人数/小时范围数据库检查；fixed 要求 deadline_on；unknown/ongoing 不存伪造精确截止。
- 日期/时刻/来源时区配对与现有赛事一致；下一次复核由 last_verified_at（无则 published_at）+30 天计算，仅对未结束的长期/未知机会。

索引：code 唯一；(publication_status,deadline_mode,deadline_on)；(category,publication_status)；(last_verified_at)。

### R03 research.ResearchSource

表名：`research_researchsource`。官方信息链接之外的补充来源；主链接唯一来源在主表 official_url，不建立第二份可编辑副本。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `opportunity` | 科研机会 | `ForeignKey(research.ResearchOpportunity)` | 否 | 写入服务指定 | PROTECT； |
| `source_url` | 补充链接 | `URLField(2048)` | 否 | 管理员/导入填写 | HTTP/HTTPS；同机会下不重复 |
| `source_name` | 来源名称 | `CharField(200)` | 否 | '' |  |
| `source_type` | 来源类型 | `CharField(16)` | 否 | unknown | unknown / official / campus；允许值：`unknown`、`official`、`campus` |
| `published_on` | 来源发布日期 | `DateField` | 是 | NULL |  |
| `updated_on` | 来源更新日期 | `DateField` | 是 | NULL |  |
| `fetched_at` | 最近获取时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `verified_at` | 来源核验时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `created_at` | 记录时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |

- 唯一 (opportunity,source_url)；不得重复主表 official_url；不强制手工补充来源名称/时间。

索引：(opportunity,created_at)。

### R04 research.ResearchRevision

表名：`research_researchrevision`。科研每个内容版本的完整快照，供追溯与快讯差异提示。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `opportunity` | 科研机会 | `ForeignKey(research.ResearchOpportunity)` | 否 | 写入服务指定 | PROTECT； |
| `version` | 版本号 | `PositiveIntegerField` | 否 | 主表 content_version | 同机会唯一 |
| `snapshot` | 该版完整内容 | `JSONField` | 否 | 构造时必填 | 固定 schema；包含公开字段、来源和分类标签当时值，不复制账号联系资料 |
| `created_at` | 版本时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `created_by` | 操作者 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT； |

- 唯一 (opportunity,version)；快照不可改写；公开接口不直接返回整包 JSON，下架后不从历史泄露内容。

索引：(opportunity,version) 唯一索引。

### S01 resources.ResourceTaxonomy

表名：`resources_resourcetaxonomy`。受控分类、标签及研究/适用方向，不与现有赛事词条合表。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `code` | 编码 | `SlugField(64)` | 否 | 管理员指定 | 唯一，建立后固定 |
| `kind` | 用途 | `CharField(12)` | 否 | 必填 | category / tag / direction；允许值：`category`、`tag`、`direction` |
| `name` | 名称 | `CharField(80)` | 否 | 必填 | 非空；同 kind 唯一 |
| `is_active` | 可供新选择 | `BooleanField` | 否 | True |  |
| `sort_order` | 排序 | `PositiveIntegerField` | 否 | 0 | 非负 |

- 唯一 code、(kind,name)；已引用词条不硬删除；kind 和 code 固定，历史版本冻结当时显示名称。

索引：(kind,is_active,sort_order)。

### S02 resources.Resource

表名：`resources_resource`。管理员维护的外链资源，无文件上传或托管字段。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `code` | 稳定编号 | `SlugField(80)` | 否 | resource-<UUID4 hex> | 唯一 |
| `title` | 资源名称 | `CharField(200)` | 否 | 必填 | 非空 |
| `description` | 资源介绍 | `TextField` | 否 | '' | MaxLengthValidator(10000)；发布必填 |
| `category` | 资源类别 | `ForeignKey(resources.ResourceTaxonomy)` | 是 | NULL | PROTECT；发布必有有效 category |
| `provider` | 来源单位或作者 | `CharField(500)` | 否 | '' |  |
| `access_url` | 访问链接 | `URLField(2048)` | 否 | '' | 发布必填 HTTP/HTTPS |
| `source_note` | 来源说明 | `CharField(1000)` | 否 | '' |  |
| `availability` | 可用状态 | `CharField(12)` | 否 | available | available / unavailable；普通失效不自动下架；允许值：`available`、`unavailable` |
| `last_verified_at` | 最近实际核验时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `publication_status` | 发布状态 | `CharField(12)` | 否 | draft | draft / published / withdrawn；允许值：`draft`、`published`、`withdrawn` |
| `published_at` | 首次发布时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `last_edited_at` | 最近内容编辑时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `withdrawal_reason` | 最近下架原因 | `CharField(500)` | 否 | '' | 下架时必有；内部；历史另存 AdminAction |
| `content_version` | 当前内容版本号 | `PositiveIntegerField` | 否 | 1 | 实际内容/关系变化递增；同事务产生完整快照 |
| `created_at` | 建档时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `updated_at` | 最近维护时间 | `DateTimeField` | 否 | timezone.now | auto_now；不作为原通知时间 |
| `created_by` | 创建人 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT；自动任务可空 |
| `updated_by` | 最近操作者 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT；自动任务本次为空，不冒用上次人员 |

- 已发布必须有 title、description、category、access_url；失效条目保留，但不提供失效访问按钮。
- 标签/方向及赛事科研关联见 J09–J12，均选填；修订与关系更新同事务产生 ResourceRevision。

索引：(publication_status,availability,category)；code 唯一。

### S03 resources.ResourceRevision

表名：`resources_resourcerevision`。资源内容及关系版本。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `resource` | 资源 | `ForeignKey(resources.Resource)` | 否 | 写入服务指定 | PROTECT； |
| `version` | 版本号 | `PositiveIntegerField` | 否 | 主表 content_version |  |
| `snapshot` | 内容快照 | `JSONField` | 否 | 构造时必填 | 固定 schema；包含关系目标编号及当时展示值 |
| `created_at` | 版本时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `created_by` | 操作者 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT； |

- 唯一 (resource,version)；不可变；下架可见性同样适用于历史快照。

索引：(resource,version) 唯一索引。

### N01 newsletters.Newsletter

表名：`newsletters_newsletter`。一期快讯的稳定身份和公开版本指针；编辑新草稿不改变已公开内容。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `code` | 稳定编号 | `SlugField(80)` | 否 | newsletter-<UUID4 hex> | 唯一 |
| `publication_status` | 发布状态 | `CharField(12)` | 否 | draft | draft / published / withdrawn；允许值：`draft`、`published`、`withdrawn` |
| `current_revision` | 当前公开版本 | `ForeignKey(newsletters.NewsletterRevision)` | 是 | NULL | PROTECT；published 必有，须属于本期且已确认 |
| `published_at` | 首次发布时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `last_edited_at` | 最后公开更正时间 | `DateTimeField` | 是 | NULL | 首次发布为空，再次确认新版时更新 |
| `withdrawal_reason` | 下架原因 | `CharField(500)` | 否 | '' | 下架必填、内部 |
| `created_at` | 创建时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `created_by` | 创建人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |

- 公开版本只有确认动作可切换；已发布原文不被未确认草稿覆盖。

索引：(publication_status,published_at)；code 唯一。

### N02 newsletters.NewsletterRevision

表名：`newsletters_newsletterrevision`。一期快讯的草稿或已确认版本；已经确认的版本不可改写。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `newsletter` | 所属快讯 | `ForeignKey(newsletters.Newsletter)` | 否 | 写入服务指定 | PROTECT； |
| `version` | 版本号 | `PositiveIntegerField` | 否 | 同一期从 1 递增 |  |
| `title` | 标题 | `CharField(200)` | 否 | '' | 确认前必填 |
| `introduction` | 导读 | `TextField` | 否 | '' | MaxLengthValidator(5000)；选填；纯文本 |
| `status` | 版本状态 | `CharField(12)` | 否 | draft | draft / confirmed；允许值：`draft`、`confirmed` |
| `created_at` | 草稿创建时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `updated_at` | 草稿更新时间 | `DateTimeField` | 否 | timezone.now | auto_now；已确认后不可修改 |
| `created_by` | 创建人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |
| `updated_by` | 编辑人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |
| `confirmed_at` | 管理员确认时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `confirmed_by` | 确认管理员 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT； |

- 唯一 (newsletter,version)；同一期最多一版 draft；confirmed 状态要求确认人/时间齐全且至少一条有效内容项。
- 已确认版本禁止增删改内容项；修改先复制新草稿，确认后原子切换主表 current_revision。

索引：(newsletter,version) 唯一；(newsletter,status)。

### N03 newsletters.NewsletterItem

表名：`newsletters_newsletteritem`。某快讯版本中的一个内容项；活动只存在于该表。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `revision` | 所属快讯版本 | `ForeignKey(newsletters.NewsletterRevision)` | 否 | 写入服务指定 | PROTECT； |
| `position` | 排序 | `PositiveIntegerField` | 否 | 从 1 排序 | 同版本唯一且>=1 |
| `kind` | 条目类型 | `CharField(16)` | 否 | 必填 | competition / research / resource / activity；允许值：`competition`、`research`、`resource`、`activity` |
| `competition` | 赛事引用 | `ForeignKey(competitions.Competition)` | 是 | NULL | PROTECT； |
| `research` | 科研引用 | `ForeignKey(research.ResearchOpportunity)` | 是 | NULL | PROTECT； |
| `resource` | 资源引用 | `ForeignKey(resources.Resource)` | 是 | NULL | PROTECT； |
| `title_snapshot` | 当期标题 | `CharField(200)` | 否 | 必填 | 不随来源更新覆盖 |
| `summary_snapshot` | 当期摘要/活动介绍 | `TextField` | 否 | '' | MaxLengthValidator(5000)；确认前非空 |
| `source_url` | 当期来源链接 | `URLField(2048)` | 否 | 确认前必填 | HTTP/HTTPS |
| `source_updated_at` | 引用时业务内容时间 | `DateTimeField` | 是 | NULL | 赛事使用其 updated_at；仅用于更正提示，不冒充来源发布日期 |
| `source_version` | 引用时业务版本 | `PositiveIntegerField` | 是 | NULL | 科研/资源引用时必有；不是跨对象裸外键，目标由上方 FK 确定 |
| `activity_time_text` | 活动时间原文 | `CharField(500)` | 否 | '' |  |
| `activity_location_text` | 活动地点原文 | `CharField(500)` | 否 | '' |  |

- 唯一 (revision,position)。competition/research/resource 类型分别且仅填对应 FK；activity 三 FK 全为空。
- 活动未知日期地点留空；非活动两 activity 字段为空；原目标下架时公开条目标题/摘要/链接一并隐藏，不靠快照继续曝光。

索引：(competition) / (research) / (resource) 外键索引。

### F01 favorites.Favorite

表名：`favorites_favorite`。用户收藏赛事、科研或资源之一；仅本人可读。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `user` | 收藏用户 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |
| `competition` | 赛事目标 | `ForeignKey(competitions.Competition)` | 是 | NULL | PROTECT； |
| `research` | 科研目标 | `ForeignKey(research.ResearchOpportunity)` | 是 | NULL | PROTECT； |
| `resource` | 资源目标 | `ForeignKey(resources.Resource)` | 是 | NULL | PROTECT； |
| `created_at` | 收藏时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |

- 数据库约束三个目标恰好一个非空；各目标分别建条件唯一 (user,target)；不保存可伪造的 target_type+裸 id。
- 取消收藏可硬删除该关系；目标 PROTECT；目标下架显示不可用而不是泄露正文。

索引：(user,created_at)；三个 (user,target) 条件唯一索引。

### G01 accounts.UserRestriction

表名：`accounts_userrestriction`。沿用已确认用户字段表，新增实现而不改变规则。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `user` | 被限制用户 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |
| `reason` | 处理理由 | `CharField(500)` | 否 | 必填 | 非空；本人和管理员可见 |
| `starts_at` | 限制开始 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `expires_at` | 原定到期 | `DateTimeField` | 否 | starts_at + 24 小时（服务计算） | starts_at+24 小时 |
| `created_by` | 处理管理员 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |
| `revoked_at` | 提前解除时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `revoked_by` | 提前解除管理员 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT； |
| `revoke_reason` | 解除理由 | `CharField(500)` | 否 | '' | 提前解除时必填 |

- expires_at=starts_at+24h；revoked_at/revoked_by 成对；有撤销时理由非空且时间不早于 starts_at。
- 有效期是动态条件；重复限制锁定用户后返回原记录，不叠加、不重置；不能拿 is_active 替代。

索引：(user,expires_at)。

### G02 governance.AdminAction

表名：`governance_adminaction`。管理员统一操作的必要记录，不建立举报、申诉或工单流程。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `action` | 操作类型 | `CharField(32)` | 否 | 必填 | publish / edit / verify / withdraw / restore / restrict / revoke_restriction / disable_account / enable_account；允许值：`publish`、`edit`、`verify`、`withdraw`、`restore`、`restrict`、`revoke_restriction`、`disable_account`、`enable_account` |
| `target_user` | 用户目标 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT； |
| `competition` | 赛事目标 | `ForeignKey(competitions.Competition)` | 是 | NULL | PROTECT； |
| `research` | 科研目标 | `ForeignKey(research.ResearchOpportunity)` | 是 | NULL | PROTECT； |
| `resource` | 资源目标 | `ForeignKey(resources.Resource)` | 是 | NULL | PROTECT； |
| `newsletter` | 快讯目标 | `ForeignKey(newsletters.Newsletter)` | 是 | NULL | PROTECT； |
| `recruitment` | 招募卡目标 | `ForeignKey(teams.Recruitment)` | 是 | NULL | PROTECT； |
| `restriction` | 关联限制记录 | `ForeignKey(accounts.UserRestriction)` | 是 | NULL | PROTECT；仅对用户限制动作；不是额外处理目标 |
| `actor` | 管理员 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |
| `created_at` | 处理时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `reason` | 必要理由 | `CharField(500)` | 否 | '' | 下架、恢复、限制/解除、停用/启用必须非空 |
| `changes` | 必要前后状态 | `JSONField` | 否 | dict（每行独立） | 固定动作 schema；不存邮件、电话、微信、密码或整个请求报文 |
| `reverses` | 被撤销的操作 | `OneToOneField(governance.AdminAction)` | 是 | NULL | PROTECT；禁止自指；用于 restore/revoke_restriction/enable_account |

- 六个目标恰好一个非空；关联限制的目标用户必须一致。
- 记录只追加；纠正使用新记录；不强制不同管理员复核，也不限制学生反馈次数。联系我们使用运营配置，不建立反馈模型。

索引：(created_at)；(target_user,created_at)；(recruitment,created_at)。

### M01 notifications.BusinessEvent

表名：`notifications_businessevent`。业务动作及条件变更的不可变事件，保存必要确认历史并可靠生成站内消息。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `event_key` | 幂等事件标识 | `UUIDField` | 否 | uuid4 | 唯一；相同业务重试复用该值 |
| `kind` | 事件类型 | `CharField(48)` | 否 | 必填 | 见说明的允许事件清单；不接受客户端任意事件名；允许值：`recruitment_edited`、`recruitment_closed`、`application_submitted`、`contact_opened`、`application_confirmed`、`confirmation_revoked`、`application_continued`、`application_withdrawn`、`application_rejected`、`application_ended`、`member_joined`、`departure_requested`、`departure_responded`、`departure_withdrawn`、`departure_completed`、`dissolution_requested`、`dissolution_responded`、`dissolution_withdrawn`、`dissolution_rejected`、`dissolution_completed`、`admin_action` |
| `actor` | 动作用户 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT；系统动作为 NULL |
| `occurred_at` | 事件时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `recruitment` | 卡片目标 | `ForeignKey(teams.Recruitment)` | 是 | NULL | PROTECT； |
| `application` | 申请目标 | `ForeignKey(teams.Application)` | 是 | NULL | PROTECT； |
| `departure_request` | 退出/移除目标 | `ForeignKey(teams.DepartureRequest)` | 是 | NULL | PROTECT； |
| `dissolution_request` | 解散目标 | `ForeignKey(teams.DissolutionRequest)` | 是 | NULL | PROTECT； |
| `admin_action` | 管理操作目标 | `ForeignKey(governance.AdminAction)` | 是 | NULL | PROTECT； |
| `payload` | 必要事件数据 | `JSONField` | 否 | dict（每行独立） | 按 kind 校验版本号、确认方、变更字段和原因；不保存联系方式，禁止原样存请求 |

- 五个目标恰好一个非空；事件种类和目标匹配；创建后不可变。
- 卡片变更、申请正式确认/撤销/资料继续及终结、退出移除/解散动作均留事件；不是每一事件都要通知本人。

索引：event_key 唯一；(application,occurred_at)；(recruitment,occurred_at)。

### M02 notifications.Notification

表名：`notifications_notification`。一个业务事件发给一名接收人的站内消息。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `event` | 业务事件 | `ForeignKey(notifications.BusinessEvent)` | 否 | 写入服务指定 | PROTECT； |
| `recipient` | 接收用户 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |
| `title` | 通知标题 | `CharField(200)` | 否 | 必填 | 非空 |
| `body` | 轻量内容 | `CharField(1500)` | 否 | 必填 | 仅当事人允许看到的内容，不复制联系方式 |
| `created_at` | 创建时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `read_at` | 首次已读时间 | `DateTimeField` | 是 | NULL | 不等于接受条件；重复已读不改首次时间 |

- 唯一 (event,recipient)；read_at>=created_at；入口由事件关联对象生成，读取时重新检查权限/版本。
- 事件、状态变化和需要的接收人记录在同一事务写入；无邮件/短信投递字段；消息仅本人可读。

索引：(recipient,read_at,created_at)。

### I01 ingestion.SourceConfig

表名：`ingestion_sourceconfig`。已获准接入的官方来源配置；采集调度由服务执行。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `code` | 来源编码 | `CharField(64)` | 否 | 必填 | 唯一且稳定 |
| `name` | 来源名称 | `CharField(200)` | 否 | 必填 |  |
| `base_url` | 官方入口地址 | `URLField(2048)` | 否 | 管理员填写 | HTTP/HTTPS；限定可抓取范围 |
| `content_kind` | 内容种类 | `CharField(20)` | 否 | 必填 | competition / research / resource / mixed；允许值：`competition`、`research`、`resource`、`mixed` |
| `adapter_key` | 采集适配器标识 | `CharField(80)` | 否 | 必填 | 服务端已注册适配器；不是可执行脚本或用户 URL 指令 |
| `is_active` | 是否启用 | `BooleanField` | 否 | False | 首次核对来源后由管理员启用 |
| `created_at` | 创建时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `updated_at` | 维护时间 | `DateTimeField` | 否 | timezone.now | auto_now |
| `maintained_by` | 维护人 | `ForeignKey(accounts.User)` | 否 | 写入服务指定 | PROTECT； |

- code 唯一；不存密钥；6 小时和手动触发是调度配置，不复制到每条内容。

索引：(is_active,content_kind)。

### I02 ingestion.FetchRun

表名：`ingestion_fetchrun`。一次获准来源页面获取；批量任务可用同一 batch_key 关联多页。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `source` | 来源配置 | `ForeignKey(ingestion.SourceConfig)` | 否 | 写入服务指定 | PROTECT； |
| `batch_key` | 批次标识 | `UUIDField` | 否 | uuid4 | 用于追踪，不表示业务内容身份 |
| `requested_url` | 实际请求地址 | `URLField(2048)` | 否 | 任务指定 | 必须落在已批准来源/重定向规则内；不记录授权信息 |
| `trigger` | 触发方式 | `CharField(12)` | 否 | 必填 | manual / scheduled；允许值：`manual`、`scheduled` |
| `triggered_by` | 手动触发人 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT；scheduled 时为空 |
| `status` | 运行状态 | `CharField(16)` | 否 | running | running / succeeded / unchanged / failed；允许值：`running`、`succeeded`、`unchanged`、`failed` |
| `started_at` | 开始时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `finished_at` | 结束时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `http_status` | 响应状态码 | `PositiveSmallIntegerField` | 是 | NULL | 有响应时 100–599；网络异常不是 0 |
| `error_code` | 错误码 | `CharField(80)` | 否 | '' |  |
| `error_summary` | 脱敏错误摘要 | `CharField(1000)` | 否 | '' |  |

- finished_at>=started_at；结束状态须有 finished_at；失败必须有错误码；无变化不制造新原文版本。

索引：(source,started_at)；(status,finished_at)；(batch_key)。

### I03 ingestion.SourceVersion

表名：`ingestion_sourceversion`。来源页面文本的一次不可变内容版本。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `source` | 来源配置 | `ForeignKey(ingestion.SourceConfig)` | 否 | 写入服务指定 | PROTECT； |
| `first_fetch` | 首次获取记录 | `ForeignKey(ingestion.FetchRun)` | 否 | 写入服务指定 | PROTECT； |
| `source_url` | 原文地址 | `URLField(2048)` | 否 | 实际获准地址 | HTTP/HTTPS |
| `title` | 原文标题 | `CharField(500)` | 否 | '' |  |
| `body_text` | 提取的原文文本 | `TextField` | 否 | 抓取结果 | MaxLengthValidator(200000)；超限记录异常，不静默截断 |
| `content_hash` | 规范化文本 SHA-256 | `CharField(64)` | 否 | 计算 | 64 位小写十六进制 |
| `source_published_on` | 来源发布日期 | `DateField` | 是 | NULL |  |
| `source_updated_on` | 来源更新日期 | `DateField` | 是 | NULL |  |
| `source_time_text` | 不完整时间原文 | `CharField(500)` | 否 | '' |  |
| `first_seen_at` | 首次获取时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `last_seen_at` | 最后重见时间 | `DateTimeField` | 否 | timezone.now | 只更新获取元数据，不改内容或首次时间 |

- 唯一 (source,source_url,content_hash)；last_seen_at>=first_seen_at；first_fetch.source 一致。
- body_text/hash/title/来源时间确定后不可改；新内容新版本，任务验证不得把抓取时间当来源时间。

索引：(source,source_url)；(content_hash)。

### I04 ingestion.ProcessingResult

表名：`ingestion_processingresult`。一次提取或快讯草稿生成的候选结果及审核决定。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `task_type` | 任务类型 | `CharField(32)` | 否 | 必填 | competition_extract / research_extract / newsletter_draft；允许值：`competition_extract`、`research_extract`、`newsletter_draft` |
| `source_version` | 提取原文版本 | `ForeignKey(ingestion.SourceVersion)` | 是 | NULL | PROTECT；两类 extract 必有；newsletter_draft 为空 |
| `ai_call` | 关联 AI 调用 | `ForeignKey(ingestion.AICall)` | 是 | NULL | PROTECT；规则提取可空；被引用调用日志不得清理 |
| `candidate` | 候选字段或条目 | `JSONField` | 否 | dict | 按 task_type 固定 schema，不能直接 mass assignment 到业务模型 |
| `evidence` | 字段/条目原文依据 | `JSONField` | 否 | dict | 原文定位/引文/输入引用，校验不等于权威核验 |
| `missing_fields` | 缺失字段名 | `JSONField` | 否 | list |  |
| `validation_errors` | 校验错误 | `JSONField` | 否 | list |  |
| `status` | 处理状态 | `CharField(12)` | 否 | pending | pending / accepted / rejected；允许值：`pending`、`accepted`、`rejected` |
| `decision_mode` | 决定方式 | `CharField(12)` | 否 | '' | '' / human / rules；允许值：`空串`、`human`、`rules` |
| `rule_version` | 受控规则版本 | `CharField(80)` | 否 | '' | rules 采纳时必填，只有赛事允许 |
| `reviewed_by` | 确认管理员 | `ForeignKey(accounts.User)` | 是 | NULL | PROTECT； |
| `reviewed_at` | 作出决定时间 | `DateTimeField` | 是 | NULL | 系统维护 |
| `created_at` | 生成时间 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `competition` | 采纳后的赛事 | `ForeignKey(competitions.Competition)` | 是 | NULL | PROTECT； |
| `research` | 采纳后的科研 | `ForeignKey(research.ResearchOpportunity)` | 是 | NULL | PROTECT； |
| `newsletter_revision` | 采纳后的快讯草稿版本 | `ForeignKey(newsletters.NewsletterRevision)` | 是 | NULL | PROTECT； |

- accepted 时对应 task_type 的唯一目标必有；其余目标为空；非 accepted 不填采纳目标。
- human 决定必须有 reviewed_by；rules 只限通过完整发布规则的赛事且 rule_version 必填。
- 科研和快讯必须人工确认；newsletter 结果采纳为草稿不等于快讯已经公开发布。

索引：(status,created_at)；(source_version,created_at)；(task_type,status)。

### I05 ingestion.ProcessingInput

表名：`ingestion_processinginput`。快讯生成时冻结的已核验业务输入，保障事后核对来源。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `result` | 所属快讯处理结果 | `ForeignKey(ingestion.ProcessingResult)` | 否 | 写入服务指定 | PROTECT； |
| `position` | 输入次序 | `PositiveIntegerField` | 否 | 从 1 排序 |  |
| `competition` | 赛事输入 | `ForeignKey(competitions.Competition)` | 是 | NULL | PROTECT； |
| `research` | 科研输入 | `ForeignKey(research.ResearchOpportunity)` | 是 | NULL | PROTECT； |
| `resource` | 资源输入 | `ForeignKey(resources.Resource)` | 是 | NULL | PROTECT； |
| `snapshot` | 输入白名单快照 | `JSONField` | 否 | 构造时必填 | title/source_url/content/业务版本或内容时间；不包含私有管理员字段 |

- 唯一 (result,position)；三个目标恰好一个非空；result.task_type=newsletter_draft；快照不可改。
- 按当前 ai_services 契约每次最多 10 条、标题正文合计最多 20000 字符，超限显式报错；活动段落管理员另行维护。

索引：(result,position) 唯一索引。

### I06 ingestion.AICall

表名：`ingestion_aicall`。一次模型调用的必要运行日志；不在现有 ai_services 服务包内定义 ORM 模型。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认/赋值方式 | 约束与用途 |
| --- | --- | --- | --- | --- | --- |
| `id` | 主键 | `BigAutoField` | 否 | 自动生成 | 数据库主键 |
| `trace_key` | 请求/重试链标识 | `UUIDField` | 否 | uuid4 | 同一逻辑任务重试可复用；不是业务外键 |
| `provider` | 服务商 | `CharField(50)` | 否 | 必填 |  |
| `model_name` | 实际模型 | `CharField(200)` | 否 | 必填 |  |
| `prompt_version` | 提示词版本 | `CharField(80)` | 否 | 必填 |  |
| `started_at` | 调用开始 | `DateTimeField` | 否 | timezone.now | 系统维护 |
| `finished_at` | 调用结束 | `DateTimeField` | 是 | NULL | 系统维护 |
| `status` | 状态 | `CharField(12)` | 否 | running | running / succeeded / failed；允许值：`running`、`succeeded`、`failed` |
| `duration_ms` | 耗时毫秒 | `PositiveBigIntegerField` | 是 | NULL | 完成时填写，非负 |
| `input_tokens` | 输入 token | `PositiveBigIntegerField` | 是 | NULL | 未知留空，不补 0 |
| `output_tokens` | 输出 token | `PositiveBigIntegerField` | 是 | NULL | 未知留空，不补 0 |
| `error_code` | 错误码 | `CharField(80)` | 否 | '' |  |
| `error_summary` | 脱敏错误摘要 | `CharField(1000)` | 否 | '' |  |

- 结束状态须有结束时间和耗时；finished_at>=started_at；失败必须有错误码。
- 被 ProcessingResult 引用的调用保留；仅无引用且结束超过 30 天的详细日志允许清理。

索引：(trace_key)；(status,finished_at)。

## 三 显式多选关联表

每表均有自动 `id: BigAutoField`，下列两个外键均非 NULL；默认不填，属于拥有方的多选关系。数据库唯一约束为两个外键的组合；各外键自带索引。拥有方删除策略 CASCADE，目标 PROTECT。

| 编号/模型 | 拥有方字段 → 模型 | 目标字段 → 模型 | Python 多选属性 | 允许目标 |
| --- | --- | --- | --- | --- |
| J01 `teams.RecruitmentCurrentSkill` | `revision` → `teams.RecruitmentRevision` | `option` → `teams.RecruitmentOption` | `current_skills` | skill |
| J02 `teams.RecruitmentRequiredRole` | `revision` → `teams.RecruitmentRevision` | `option` → `teams.RecruitmentOption` | `required_roles` | role |
| J03 `teams.RecruitmentRequiredSkill` | `revision` → `teams.RecruitmentRevision` | `option` → `teams.RecruitmentOption` | `required_skills` | skill |
| J04 `teams.RecruitmentCampus` | `revision` → `teams.RecruitmentRevision` | `option` → `teams.RecruitmentOption` | `campuses` | campus |
| J05 `teams.ApplicationDesiredRole` | `revision` → `teams.ApplicationRevision` | `option` → `teams.RecruitmentOption` | `desired_roles` | role |
| J06 `teams.ApplicationSkill` | `revision` → `teams.ApplicationRevision` | `option` → `teams.RecruitmentOption` | `skills` | skill |
| J07 `research.ResearchTag` | `opportunity` → `research.ResearchOpportunity` | `taxonomy` → `research.ResearchTaxonomy` | `tags` | tag |
| J08 `research.ResearchDirection` | `opportunity` → `research.ResearchOpportunity` | `taxonomy` → `research.ResearchTaxonomy` | `directions` | direction |
| J09 `resources.ResourceTag` | `resource` → `resources.Resource` | `taxonomy` → `resources.ResourceTaxonomy` | `tags` | tag |
| J10 `resources.ResourceDirection` | `resource` → `resources.Resource` | `taxonomy` → `resources.ResourceTaxonomy` | `directions` | direction |
| J11 `resources.ResourceCompetition` | `resource` → `resources.Resource` | `competition` → `competitions.Competition` | `competitions` | 真实存在的业务对象 |
| J12 `resources.ResourceResearchOpportunity` | `resource` → `resources.Resource` | `opportunity` → `research.ResearchOpportunity` | `research_opportunities` | 真实存在的业务对象 |

表名均为 app 名、下划线、小写模型名，例如 `teams_recruitmentcurrentskill`。词条新选择必须启用，已有历史不因停用而消失；所属类型在 full_clean 中校验。版本引用的关联在版本生效后冻结。意向角色可为空；有值时须属于所接受卡片版本的角色集合。

## 四 计算结果：不重复建列

| 展示或判定 | 计算依据 |
| --- | --- |
| 当前已有成员数 | 当前卡片版本 existing_member_count 减去该版本 BaselineMember 中已退出的人数；基数不含经本卡加入的成员 |
| 本卡成功应募人数 / 剩余名额 | 本卡申请形成的有效 Membership 数 / recruitment_quota 减该数；正式确认之前不占名额 |
| 当前队伍总人数 | 当前已有成员数加本卡有效应募人数；不得把申请人、线下成员重复相加 |
| 卡片满员/到期/解散暂停 | 名额、expires_at、关闭/下架字段、队伍状态与赛事状态组合；满员本身不写 closed_at |
| 申请挂起 | 未完成申请接受的 RecruitmentRevision 不是卡片 current_revision，或队伍有 pending 解散请求 |
| 联系方式可见 | 只判断双方关系、contact_opened_at、申请或成员状态，再读取 User 当前联系资料；不存联系快照 |
| 科研结束/待复核 | 来源截止精度、closed_at，以及长期/未知项目最近核验或首次发布时间加 30 天 |
| 收藏占位与快讯来源变化 | 目标当前发布状态，以及快讯存的 source_updated_at/source_version |
| 24 小时业务限制 | starts_at ≤ 当前时刻 < expires_at 且 revoked_at 为空；不使用 is_active 代替 |
| 邮箱验证状态 | 后续接入 allauth 的 EmailAddress；本轮不重复建立验证码表或 verified 列 |
