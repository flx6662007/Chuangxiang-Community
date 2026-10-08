# 工程整理记录

日期：2026-10-08。基线：`02602414`。整理分支：`codex/organize-project-20261008`。

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
