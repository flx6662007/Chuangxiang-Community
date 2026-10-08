# 项目接续说明

本文件说明开发约定。功能与配置以当前源码、[README](README.md)、[团队进度](docs/progress.md)及最新交付文档为准；[历史进度](docs/archive/progress-through-20261007.md)中的本机数量、端口、测试结果不代表当前环境。

## 接续顺序

1. 检查实际目录、分支、`git status`、远端和最近提交，阅读 [AGENTS.md](AGENTS.md)。保留团队未提交改动，不切换或清理正在运行的工作区。
2. 先读对应功能源码和文档；区分代码已实现、资料已导入、环境已配置和实际部署已验证。
3. 改动后运行相关测试和路径检查，说明已知失败及本次新增问题。
4. 按用户授权执行提交、推送和部署，分别核实结果；不把 Git 同步说成数据库或运行环境同步。

## 主要入口

| 内容 | 入口 |
| --- | --- |
| 当前结构与请求链路 | [代码导读](docs/code-guide.md)、[后端目录](backend/README.md)、[前端说明](frontend/README.md) |
| 环境与内测 | [后端开发](docs/backend-development.md)、[邀请内测](docs/private-beta.md) |
| 赛事与资料 | [赛事助手交接](docs/ai-assistant-handoff.md)、[统一检索维护](docs/competition-search-handoff.md) |
| 科研与 AI | [科研交付](docs/releases/research-ai-20261007.md)、[AI 接入](docs/ai-v3.md)、[多轮与联网更新](docs/ai-optimization-20261008.md) |
| 接口与数据库 | [文档导航](docs/README.md)、[数据库字段](docs/database-fields.md) |

## 工程约定

- 前端为 Vue 3 / JavaScript / Vite，后端为 Django / DRF，数据库为 PostgreSQL。三人按前端、后端和数据库主责协作，共用一个仓库和后端工程。
- 账号采用 django-allauth Headless、Session 与 CSRF。保持 `AUTH_USER_MODEL='accounts.User'`；不在用户表复制邮箱核验布尔值。
- 模型修改者生成迁移并与数据库负责人对齐，其他成员执行已有迁移；不删除迁移或清空数据来处理冲突。
- 浏览器只调用后端 API。公开卡片不返回私人联系方式和内部处理记录；写操作由后端校验身份、权限、版本和业务状态。
- 组队围绕具体赛事届次；当前或下一届可否组队由 `competitions/recruitment_policy.py` 等业务规则决定，不等同于官方是否正在报名。写入沿用事务服务和既有锁顺序。
- 科研资料展示、详情与检索使用 `research` 和信息库公共接口；是否开放取决于 `PUBLIC_RESEARCH_ENABLED`。申请前往官方入口，不新增站内科研申请业务。
- 赛事与学习资源以人工资料包导入为主，历史采集保留供维护。卡片读取已保存字段，不把采集或模型调用放进普通列表请求。
- 首页聊天、赛事向导使用服务端 `DEEPSEEK_*`；原内部草稿单独由 `AI_ENABLED` 等控制。赛事索引与科研/资源统一索引分别维护，资料更新后按文档重建。
- 快讯由公共内容文件维护；`editorial.json` 只放允许公开的信息。真实密钥、账号、数据库、模型、索引与运行日志放在被忽略的本地目录。
- 资料包、来源快照、哈希清单和正式交付物是可重建依据；不要按文件名、扩展名或重复哈希删除。重组时同步修正文档链接及脚本引用。

解释面向正在学习开发的团队，先说明功能与实际操作，再介绍必要术语。
