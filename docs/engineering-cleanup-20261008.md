# 工程整理记录

日期：2026-10-08。本文前半部分记录文档整理，后半部分记录代码职责整理；两轮分别验证。文档整理基线：`02602414`，分支：`codex/organize-project-20261008`。

## 整理方案

本轮调整文档组织和本地产物忽略规则。保留业务代码、依赖版本、数据库迁移、启动脚本及资料包路径；原内测工作区独立保留。

| 操作 | 范围 | 原因 |
| --- | --- | --- |
| 更新入口 | 根 README、`agent.md`、文档导航、前后端说明、代码导读 | 统一当前功能、启动和维护入口，移除过时状态描述 |
| 更新 AI 与信息库说明 | AI 服务、V3 接入、信息库、后端开发 | 区分聊天与旧草稿配置、两类索引、科研开关和可选联网搜索 |
| 归档阶段记录 | 3 份 9 月 26 日验收、9 月 29 日提取记录、早期前后端/UI 方案、两轮任务、9 月 25 日数据库验收、基础聊天记录 | 集中到 `docs/archive/`，保留内容与追溯入口 |
| 拆分进度 | 原进度全文移到 `docs/archive/progress-through-20261007.md`，`docs/progress.md` 保留当前摘要 | 避免旧本机数量和历史测试被当作现在的部署状态 |
| 删除系统元数据 | 根、`backend/`、`frontend/`、`frontend/src/` 的 4 个 `.DS_Store` | macOS 文件夹显示缓存，非工程输入，已在忽略规则内 |
| 补充忽略规则 | 本地环境文件、日志、数据库导出、索引及内测凭据清单 | 避免放到约定目录之外时误提交 |
| 修正引用 | 上述文件的入链和内部相对链接 | 文件归档后导航、文档引用仍指向实际文件 |

## 保留范围

- `frontend/`、`backend/`、`scripts/`、`deploy/` 的程序与启动路径保持原样。
- 赛事与科研导入包、原始来源、哈希清单、评测数据、正式 ZIP/HTML/XLSX 交付物保留。相同文件可能分别承担原包和重建输入，不按扩展名或重复哈希批量删除。
- 数据库模型和全部迁移、前后端测试、锁文件保留。
- 原 `Chuangxiang-Community-beta-ai` 的科研工具与 Skills 修改仍在原工作区；本轮不将未提交改动混入纯主分支整理。
- `database-handoff.md` 仍承载初始化引用，`ai-v2.md` 含后续有效接入步骤，保留原路径并标明阅读关系。

## 验证

| 检查 | 实际结果 |
| --- | --- |
| 前端安装 | `npm ci` 成功，`package.json` 和锁文件未变化 |
| 前端测试 | `npm test`：71 项中 70 项通过、1 项已有失败；在业务源码未修改的基线上复现 |
| 前端构建 | `npm run build` 成功 |
| Django 系统检查 | `python manage.py check --settings=config.test_settings`：无问题 |
| 迁移一致性 | `python manage.py makemigrations --check --dry-run --settings=config.test_settings`：无遗漏迁移 |
| 后端相关测试 | `python manage.py test config information_library.test_public_api ai_services.test_status --settings=config.test_settings --noinput`：55 项通过 |
| 文档链接 | 451 条本地 Markdown 链接全部指向现存文件/目录；未检查标题锚点和外部网站可达性 |
| 资料完整性 | 306 个受保护资料文件无丢失、无内容改动；同时核对 Git 差异与换行归一后的 SHA256 |
| 工程完整性 | 927 个业务源码、启动脚本、迁移、锁文件及配置文件未变化 |
| 忽略规则 | 19 项检查通过；4 份 `.env.example` 仍可跟踪 |
| 差异格式 | `git diff --check` 通过 |

测试在本次整理目录运行。后端复用已安装的 Python 依赖，以 `config.test_settings` 使用隔离的内存 SQLite，不连接现有内测 PostgreSQL；前端使用 Node.js 24.15.0、npm 11.12.1。没有进行真实模型调用、邮件投递、双账号浏览器验收或生产部署，不据此宣称整站全量验收通过。

### 已有问题

1. `frontend/tests/aiResponse.test.js` 的“站内记录编号和详情路由在聊天来源中保留”失败：当前 `parseAIReply()` 未完整保留科研/团队的站内路径与记录编号。首个断言为预期 `/research/19`、实际 `null`；相关团队来源和推荐也需要一起核对。该问题来自整理前主分支，本轮未改业务代码或测试。
2. 安装依赖时，npm 审计报告间接依赖 `source-map-js@1.2.1` 存在一项高危公告 `GHSA-68fv-2mgg-jv7q`。本轮按范围约定保留依赖与锁文件，后续单独评估修复。
3. 内测工作区的科研工具/Skills 修改尚未进入这份主分支；后续升级内测时需单独整合。科研资料、模型、索引、搜索服务和实际数据库不会随本轮 Git 提交部署。

本机审计脚本、基线和明细留在被忽略的 `.local/engineering-cleanup/`，共享仓库仅保存这份范围与结果说明。

## 发布约定

用户已在本轮明确授权整理后提交并推送 `main`。仅推送本轮整理变更；推送前再次获取远端，保留队友新增提交，不强制推送。

## 代码职责整理

基线：`2d11835`，分支：`codex/clarify-module-responsibilities`。检查覆盖后端业务模块、AI 调用关系和前端请求目录。目标是统一共用实现、修正职责归属；不同业务的数据模型继续独立。

### 修改

| 内容 | 调整 | 原因 |
| --- | --- | --- |
| 科研导入 | `curation/management/commands/import_research_materials.py` 与科研导入测试迁入 `research/` | 命令保存科研机会，属于科研业务；命令名与参数保持不变 |
| 公共文本 | 清理函数迁至 `common/public_content.py` | 科研、资源及 AI 不必为了两个函数加载信息库查询和模型 |
| API 基础 | 输入检查、分页、错误和视图基类迁至 `common/` | 举报、通知、资源等无需依赖组队或赛事视图才能处理通用请求 |
| 模型基础 | `CleanFieldsModel` 迁至 `common/model_base.py` | 消除 `common.models` 对赛事模型的反向依赖 |
| 保存助手 | 相同的校验保存实现集中到 `common/persistence.py` | 复用实现；业务服务继续管理事务、锁和权限 |
| 可见范围 | 组队与公开赛事查询迁入各自 `selectors.py` | AI、举报和检索直接复用查询，不导入 HTTP 视图 |
| 资料读取 | `LibraryReadMixin` 迁至 `curation/api.py` | 资源、目录和知识文档复用同一读取行为与预览权限 |
| 采集锁 | 来源锁迁至 `ingestion/locks.py` | 目录采集不用导入整个采集服务；锁键和释放逻辑不变 |
| 前端请求 | `src/services/` 的 4 个文件归入 `src/api/`，关键词检索更名为 `catalogSearch` | 请求入口统一，关键词检索与模型聊天区分清楚 |
| 前端共用 | `api/csrf.js`、`utils/pagination.js` 统一令牌和页码处理 | 避免通过账号模块取令牌或重复实现同一页码规则 |
| 无引用文件 | 移除旧 `mocks/aiCompetitionSearch.js` | 全仓无调用方；当前首页视觉预览数据继续保留 |

旧公共 Python 导入入口保留兼容导出；项目内生产消费者直接引用新位置。迁移历史、表名、字段、接口 URL、CLI 名称、依赖和启动命令未改变。科研和赛事资料包、来源快照、原始交付文件保持原样。

`curation/test_research_delivery.py` 验证的是赛事目录 90—130 的交付包，因此继续归属 `curation/`。账号资格、各业务发布规则、快讯版本、网络抓取验证和公开展示字段虽有相似代码，但处理不同条件，本轮保留。AI 聊天与赛事向导也保留独立流程。

### 验证方法

使用独立 PostgreSQL 17 集群和测试数据库，对比基线与整理后的完整后端测试。测试使用本地邮件后端和模型替身；测试凭据、日志与基线源码只保存在被忽略的 `.local/responsibility-refactor/`。既有内测数据库、配置、进程和临时网址未调整。

前端执行 `npm test` 与 `npm run build`；后端执行 `manage.py test --settings=config.postgres_test_settings --noinput`，另做 `check` 和 `makemigrations --check --dry-run`。共用函数及导入命令还与基线比较 AST；静态检查生产代码中的旧引用和文档链接。

### 验证结果

| 检查 | 结果 |
| --- | --- |
| 整理前后端完整测试 | 846 项：842 通过、3 跳过、1 错误 |
| 整理后后端完整测试 | 863 项：859 通过、3 跳过、1 错误；新增 17 项全部通过 |
| 后端前后对比 | 唯一错误相同，未发现新增失败；PostgreSQL 锁与组队并发测试已执行 |
| 前端测试 | 71 项：70 通过、1 项与基线相同的失败 |
| 前端构建 | 成功；迁移后的相对导入均可解析 |
| Django 系统检查与迁移 | 无系统检查问题，无遗漏迁移 |
| 路径与保留范围 | 442 条本地文档链接有效；382 个资料、迁移、依赖及启动脚本路径无本轮改动，受保护资料和迁移无缺失 |
| 差异与配置 | `git diff --check` 通过；配置、测试凭据和日志未进入提交范围 |

后端唯一错误是 `ai_services.test_unified.UnifiedRetrievalTests.test_public_open_team_card_is_searchable_and_links_to_real_detail`：智能检索已取得的队伍记录被后续类型筛选排除，测试寻找该队伍时触发 `StopIteration`。基线与整理后的错误及调用位置一致，应单独修复。前端来源解析问题见前文“已有问题”。三项后端跳过均为需要显式指定真实交付包的测试；其他资料导入测试正常执行。

本轮未调用真实模型或投递邮件，也未重新部署内测。Git 同步后仍需按目标环境的配置和资料状态部署，不能将本次测试结果等同于线上功能已全部启用。
