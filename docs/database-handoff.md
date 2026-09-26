# 数据库开发交付说明

**历史交付说明：**下文保留 2026-09-25 数据库分支交付时的原始记录，其中“待合并”“尚未接入”等仅描述当时状态。该交付已合入主分支；后续另行接入认证、组队、采集等业务，并于 2026-09-26 通过 `governance.0004` 增加 `Report`、`Appeal`。因此下文“不建举报／申诉”和表数、迁移数、测试数均不是当前现况。最新实现、合并及运行验收见[团队进度](progress.md)，新增治理字段见[业务模块字段表](remaining-fields-table.md)，接口见[举报与申诉](api-governance.md)。

记录日期：2026-09-25。分支：`database/round1-models`。本文件回应《数据库开发交付要求.md》，汇总数据库负责人截至本轮的实际成果及交接事项。原要求位于项目资料目录，本轮没有修改原文件。

**本地流程已完成：字段确认与正式表 → 建模 → 生成迁移 → PostgreSQL 建表 → 约束验证 → 虚构样例与导入。** 后续模型已按本轮确认范围一起完成。交付分支为 `database/round1-models`；后端审阅、PR 和合入 `main` 待完成。数据库验收不表示网站业务已上线。

## 一 对照原交付要求

| 原要求 | 本轮实际交付与证据 | 状态及接续 |
| --- | --- | --- |
| 确定用户、赛事字段及说明 | [用户字段表](user-fields-table.md) / [说明](database-fields.md#accounts)，[赛事字段表](competition-fields-table.md) / [说明](database-fields.md#competitions)；新增 [剩余模块正式字段表](remaining-fields-table.md) / [说明](database-fields.md#teams) | 用户确认的业务口径已落表；后端仍需审阅接口映射和技术实现选择 |
| 编写用户模型，明确邮箱验证关联 | [accounts/models.py](../backend/accounts/models.py)、管理器和验证器；自定义邮箱登录、规范化、唯一性、系统代号和联系资料；新增 [UserRestriction](../backend/accounts/restriction.py) | 模型和迁移已实现；allauth 单一验证状态的方案已确认，实际接入待后端 |
| 编写赛事模型 | [competitions/models.py](../backend/competitions/models.py)：届次、来源、分类/标签、精度明确的截止、发布和招募边界 | 已建表并验证；未知日期可空，不编造截止时刻 |
| 生成并提交对应迁移 | 用户/赛事初始迁移及本轮 15 个后续迁移文件；工程共 17 个项目迁移，连同 Django 内置共应用 35 项 | 生成、应用和验证完成；模型、迁移、测试和正式文档随本次提交交付，后端审阅与合并待完成 |
| 虚构样例与可重复导入 | `seed_demo_data`、`seed_remaining_demo_data`；开发库实际已导入；重复执行、保留人工修改及中途失败回滚测试通过 | 原第一轮数据保留；第二轮覆盖全部新增表；不含真实学生资料或外部抓取 |
| 检查数据约束 | PostgreSQL 108 项测试全通过；SQLite 共 108 项，106 通过、2 项 PostgreSQL 专用检查跳过；[核验报告](database-verification-2026-09-25.json) | 直接数据库写入拒绝、模型校验、实际目录约束/索引及样例导入均有验证；未宣称 HTTP/并发事务流程已实现 |
| 初始化说明并在空开发库验证 | [初始化与复现](#initialization)及下文完整命令；独立临时空 PostgreSQL 数据库成功执行全部迁移及两轮导入 | 空库初始无表；重复导入行数不变；验证后已删除本次创建的临时库，开发库保留 |

## 二 已实现的数据范围

| 模块 | 已实现内容 | 代码入口 |
| --- | --- | --- |
| 用户、赛事 | 既有用户、赛事、来源、词条；新增 24 小时限制记录 | [accounts](../backend/accounts/models.py)、[competitions](../backend/competitions/models.py) |
| 组队 | 队伍、招募卡及内容版本、基数成员、申请及资料版本、正式成员、退出/移除、解散请求及回应、六种多选关联 | [teams/models.py](../backend/teams/models.py)、[关系校验](../backend/teams/validation.py) |
| 科研 | 科研机会、来源、独立分类/标签/方向、内容快照；最少人工必填，不强制结构化 | [research/models.py](../backend/research/models.py) |
| 资源 | 资源、词条、快照，赛事/科研的可选多重关联 | [resources/models.py](../backend/resources/models.py) |
| 快讯与收藏 | 快讯草稿/确认版本、固定摘要内容项；三类内容收藏，真实外键和去重 | [newsletters](../backend/newsletters/models.py)、[favorites](../backend/favorites/models.py) |
| 通知与治理 | 不可变业务事件、收件人消息、已读时间、管理操作及撤销关联；不建举报/申诉/工单模型 | [notifications](../backend/notifications/models.py)、[governance](../backend/governance/models.py) |
| 采集与 AI 追溯 | 来源配置、抓取日志、原文版本、处理候选、快讯输入及 AI 调用元数据 | [ingestion/models.py](../backend/ingestion/models.py) |

新增 32 张主体/历史表与 12 张显式多选关联表，合计 **44 张新表**。开发库现为 **58 张表**，其中 51 张为项目表及项目关联表，另 7 张为 Django 内置表。没有默认 `auth_user`，没有 allauth 表；现有 User/Competition 字段没有重建。模型声明的 209 个命名约束与 46 个普通索引已逐项核对；主键、外键和自动唯一索引另由数据库/Django维护，不包含在这两个数字里。

`accounts.UserRestriction` 放在 restriction.py 并从 models.py 导入，Django 模型名仍是 `accounts.UserRestriction`。公共模型工具在 `common/`，无独立表。退出/移除共用 DepartureRequest；既有线下成员只保存人数，不要求建立个人账号。

### 校验落实在哪一层

| 层次 | 本轮已落实 | 不能据此宣称已完成 |
| --- | --- | --- |
| 数据库 | NULL、真实外键、唯一/条件唯一、枚举、版本正数、单一目标、确认配对、固定 24 小时、状态与时间/原因配对等 | 跨表人数上限、动作权限、完整收件人、到期批量联动 |
| 模型 | full_clean 关系一致性、历史不可改、版本递增、词条用途、校区装配、人数边界、JSON 形状与快照字段范围等 | full_clean 不自动形成事务，也不自动运行于 QuerySet.update/bulk_create/M2M.add |
| 计算属性 | 当前名额/基数、申请挂起、联系权限判定、科研待复核、收藏可用性、快讯来源可见性/更新提示 | 属性不是对外接口；接口仍需鉴权、序列化白名单和新鲜查询 |
| 测试与工具 | 独立测试库、实际结构检查、可重复虚构导入、空库完整迁移验证 | 全站功能、邮箱收件、并发抢最后名额、定时任务执行及管理页面联调 |

除已有 User 的专用保存逻辑外，业务模型遵循项目约定：服务在事务内调用 full_clean 再 save，数据库约束处理可直接表达的底线。多选关系须校验显式 through 模型后写入；`.add()` 和批量/直接 SQL 会绕过 Python 校验。已生效版本的关联删除、完整快照生成与权限同样由受控服务负责。`teams/demo_data.py` 是模拟数据装配程序，**不能当作正式的组队或管理员接口服务复用**。

<a id="initialization"></a>

## 三 队友初始化与复现

先按[后端开发说明](backend-development.md)准备 Python 依赖、自己的 PostgreSQL 开发库和登录用户，将库所有者设为该用户；配置本机 `backend/.env`。继续使用 `AUTH_USER_MODEL='accounts.User'`。不共享密码、本机虚拟环境、真实数据库备份或 `.local/`。

在 `backend` 目录执行（Linux 替换为 `.venv/bin/python`）：

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py seed_demo_data
.\.venv\Scripts\python.exe manage.py seed_remaining_demo_data
.\.venv\Scripts\python.exe manage.py verify_database_schema
```

两条 seed 命令仅限 `DJANGO_DEBUG=1`。只有迁移需同步表结构；队友获取全部迁移文件后直接 migrate，不另写建表 SQL、不重新生成已有初始迁移、不用 `--fake`。多个 `0002_initial` / `0003_initial` 是 Django 为跨模块依赖生成的完整迁移链，须全部保留。

<a id="database-tests"></a>

### 测试库与约束验证

测试使用真实迁移及独立 `test_` 数据库，本机已预建 `test_chuangxiang_dev`，不在开发库保存测试数据。测试配置中的快速密码哈希和内存邮件后端只用于测试。其他电脑无 CREATEDB 权限时，由管理员先创建空测试库并指定开发角色为所有者：

```sql
CREATE DATABASE test_chuangxiang_dev OWNER chuangxiang_dev;
```

再运行：

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.postgres_test_settings --keepdb --noinput
.\.venv\Scripts\python.exe manage.py test --settings=config.test_settings --noinput
```

若开发账号具有 CREATEDB 权限，可去掉 `--keepdb`，由 Django 创建和销毁测试库。`--keepdb` 只能指向专用测试库，不在其中存放需要保留的数据；不能用测试配置启动开发服务。

`verify_database_schema` 只读检查迁移、表、列可空性、外键、命名约束与索引，并输出行数。完整空库复现工具为 [verify_fresh_database.py](../backend/scripts/verify_fresh_database.py)：使用本机管理员配置（若存在）或具有建库权限的开发角色，新建 UUID 命名的独立临时库，完整 migrate、两轮导入并重复导入，最后仅删除本次创建的临时库。它不替换或清空日常开发库；普通队友初始化无需运行此额外验收工具。

<a id="demo-data"></a>

## 四 已导入的虚构样例

| 数据 | 开发库实际数量 / 覆盖场景 |
| --- | --- |
| 用户 | 15 个禁用、不可登录的虚构账号；第一轮 3 个，第二轮新增 12 个，无管理员权限 |
| 赛事 | 29 条：26 条公开、2 条草稿、1 条下架，公开数量超过每页 10/20 条；保留第一轮缺日期与不同时区场景 |
| 科研 / 资源 | 各 4 条：公开、草稿、下架；科研含原文最小填写、未知截止待复核和已截止，资源含外链失效 |
| 队伍 / 招募卡 | 各 3 条：编辑后的招募、解散等待、已解散；卡片共 4 个版本 |
| 申请 / 成员 | 各 6 条：加入、撤回、已开放联系后挂起、尚未开放联系后挂起，以及已退出成员 |
| 退出 / 解散 | 2 条退出或移除请求，覆盖超时完成和等待；2 条解散请求，覆盖等待与仅招募者直接完成；1 条成员回应占位 |
| 快讯 / 收藏 | 1 期快讯、2 个版本（已确认及新草稿）、4 个内容项（含活动段落）；3 条收藏（含下架占位） |
| 消息 / 治理 | 6 个业务事件、10 条站内通知、1 条限制及 1 条管理操作 |
| 采集追溯 | 1 个默认停用来源、2 条模拟抓取、1 个原文版本、2 个处理结果、3 条输入引用、1 条模拟 AI 调用记录 |

稳定编码前缀为 `demo-r1-` / `demo-r2-`，内容标题含“【虚构样例】”，链接使用 `example.org`。第二轮邮箱为 `cxdemo-r2-001@tongji.edu.cn` 至 `cxdemo-r2-012@tongji.edu.cn`，学校域名仅用于满足约束，不代表真实归属或已验证。模拟处理人外键也引用禁用样例账号，没有授予管理权限。

样例不发信、不抓取、不调用外部 AI。演示时间相对首次导入生成，重复导入不刷新期限或核验时间。第二轮整批事务创建，已存在时整批跳过，保留人工修改；标识冲突或根记录不完整报错并保留现状，不自动修补业务历史。导入不是生产导数入口。

实际结构和行数见[验收 JSON](database-verification-2026-09-25.json)。开发库与独立空库导入后的每表数量相同；空库迁移、重复导入及临时库清理均已执行成功。UTC 验证时间在报告中原样记录，对应本地 2026-09-25。

### 赛事样例导入命令

开发配置 `DJANGO_DEBUG=1` 下执行：

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo_data
```

命令源码见 [`seed_demo_data.py`](../backend/competitions/management/commands/seed_demo_data.py)。默认首次导入内容：

| 对象 | 数量与内容 |
| --- | --- |
| 用户 | 3 个虚构账号，分别演示空联系方式、微信号、电话号码 |
| 赛事 | 28 条：25 条 `published`、2 条 `draft`、1 条 `withdrawn` |
| 词条 | 6 个：3 个分类、3 个标签 |
| 来源 | 30 条，其中 26 个主来源和 4 个校内辅助来源 |
| 标签关联 | 26 条 |

赛事与词条编码统一以 `demo-r1-` 开头，展示名称含 `【虚构样例】`；所有来源与报名 URL 均使用 `https://example.org/` 占位，不抓取网站。核验时间是模拟字段，不表示核实了真实通知；采集时间保持为空。

虚构邮箱为 `cxdemo-r1-001@tongji.edu.cn` 至 `cxdemo-r1-003@tongji.edu.cn`，采用学校域名是为了符合现有约束，不表示邮箱真实存在或归属已验证。这些用户全部 `is_active=False`、非管理员，密码不可用；命令不发送邮件，不访问外部服务。演示电话号码使用 `+1 202-555-0100`，微信号为 `fictional_demo_02`。

公开样例以 6 条为一组覆盖：未知截止日期、仅日期、`Asia/Shanghai` 精确时刻、报名已截止但继续公开、固定偏移 `-05:00` 的提交时刻，以及带校内来源的校内安排。个人赛、团队赛、两者兼容和形式未知均有样例；部分团队样例模拟开启招募。两条草稿分别为最小草稿、部分资料草稿，下架样例保留首次发布时间与原因。

时间相对首次导入当天生成。重复运行保留原有 ID、系统代号、首次发布时间、核验时间、截止日期以及人工修改，不会自动延长期限或重置样例。已过期的招募由模型实时判定关闭。

命令按邮箱、赛事编码和词条编码识别已有记录；来源和标签随新赛事一起创建，已有赛事整体跳过。整个导入位于一个事务中；遇到非样例编码占用、样例词条停用或其他校验失败时整批回滚，不覆盖冲突数据。命令不删除记录；减少数量参数也不会减少已导入记录。

当前接口页大小尚未确定。25 条公开样例可验证每页 10 或 20 条时的跨页行为；若最终页大小更大，使用高于页大小的数量，例如：

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo_data --published-count 51
```

支持 1–500 条公开样例，仅补充缺失编码。该命令是串行执行的开发初始化工具，不能替代管理后台或生产环境的发布服务。

<a id="validation-results"></a>

### 验收记录

| 日期 | 迁移 / 表 | PostgreSQL 测试 | SQLite 测试 |
| --- | --- | --- | --- |
| 2026-09-24 | 20 项 / 14 张 | 75 项通过 | 74 项通过、1 项专用检查跳过 |
| 2026-09-25 | 35 项 / 58 张 | 108 项通过 | 106 项通过、2 项专用检查跳过 |

环境为 Python 3.13.13、Django 5.2.17、PostgreSQL 17.11。重复邮箱、非规范邮箱、人数范围颠倒、缺失配套日期和非法发布状态的数据库拒绝行为已验证；原有用户/赛事样例通过 full_clean，重复导入字段保持不变，异常导入整批回滚。全部模型的命名约束与索引核验及空库结果见[验收 JSON](database-verification-2026-09-25.json)。

## 五 后续交付与分工

数据库本轮可交接的文件包括模型与配置、完整迁移链、测试、两条样例命令、结构核验/空库复现工具、三份正式字段表、字段与业务规则说明、本文件及相关进度更新。`.env`、`.local/`、数据库记录、虚拟环境不提交；此前明确仅本地保留的讨论大纲不自动纳入共享。提交包需先核对新增文件清单，避免将本地讨论稿带入仓库。

| 接续事项 | 负责人 / 验收边界 |
| --- | --- |
| 本轮 Git 提交、同步后端审阅、PR 与合并 | 模型、迁移、样例及文档随本次提交交付；后端审阅、PR 和合并待完成 |
| 公开查询与 Admin | 后端：赛事/科研/资源/快讯公开筛选，草稿/下架隔离，分页；自定义用户和业务管理表单 |
| 组队与治理事务 | 后端：鉴权、统一锁序、满员并发控制、双方版本确认、继续申请、跨队申请终结、退出/解散结算、事件与完整收件人同事务、限制不叠加/不重置、账号关闭与会话失效 |
| 邮箱验证 | 后端：锁定并接入 django-allauth Headless 及迁移、验证路由、当前主邮箱一致性、验证码参数/限流、发信配置和真实收件测试；业务规则与状态归属已确认，功能未实现 |
| 采集与 AI 入库 | 后端 / 对应负责人：允许来源与适配器、6 小时调度、抓取去重、脱敏、候选核验与管理员确认，真实服务联调；日志模型已有，不代表任务已运行 |
| 页面与联调 | 前后端：字段标签、状态展示、变更提醒与继续/撤回、双方联系权限及当前值、下架占位、后台可视维护 |
| 运营配置 | 实际“联系我们”入口、角色/技能/校区及内容词库；当前样例词条不作为正式运营词库 |

邮箱模块的结论是：**业务规则已确认，用户基础已实现；验证依赖、验证码具体配置、发信和真实收件尚未完成。** 不新增第二套 verified 列或验证码表。详细接入要求见[邮箱验证实施说明](backend-development.md#email-integration)。

后端接入新服务后再补真实事务、并发、权限和接口测试；现有数据库测试提供底线，不能替代这些后续验收。字段或约束如经团队评审调整，应新增迁移并同步正式表和本交付说明，避免只改代码或只改文档。
