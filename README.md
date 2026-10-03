# 创享平台 · Chuangxiang Community

面向学生的科创信息与参赛组队网站。前端使用 Vue，后端使用 Django / DRF，数据库使用 PostgreSQL。

## 先从这里看

| 想了解什么 | 入口 |
| --- | --- |
| 第一次读代码，从哪个文件开始 | **[代码导读](docs/code-guide.md)** |
| 目前完成了什么、是否已上传 | [团队进度](docs/progress.md) |
| 怎么安装和启动 | [后端开发](docs/backend-development.md) · [前端开发](frontend/README.md) |
| 前后端怎么对接 | [赛事与账号 API](docs/api.md) · [组队 API](docs/api-teams.md) |
| 查赛事资料与学习资源 | [人工赛事资料](docs/competition-research/README.md) · [目录 1—89](docs/competition-research/tongji-2026-001-089/README.md) |
| 查其他说明 | [文档导航](docs/README.md) |

## 目前能做什么

- **信息中心**：赛事列表、搜索、详情和官方项目招募线索；首页保留人工快讯。
- **参赛组队**：发布招募、申请、双方确认入队和成员管理。
- **账号与反馈**：学校邮箱账号、站内通知、登录用户的举报与申诉。
- **管理与采集**：按学校 2026 版目录监测 255 项全学科赛事，保存官网原文与 PDF/DOCX 附件；规则提取字段并核验上架，缺项和冲突留在后台。AIC、NCDA 保留专用采集，具体流程见[赛事提取与上架](docs/catalog-publication.md)。

同济2026目录131—255的人工赛事资料、学习资源及离线入库方法，见[赛事资料与入库交付说明](docs/curated-competition-package.txt)。资料包按交付清单单独传输，导入后保留为草稿。

目录1—89的[人工资料包](docs/competition-research/tongji-2026-001-089/README.md)已按同一 `curation` 流程适配，包含89份赛事摘要、212条学习导读及来源，提供阅读索引和离线导入清单。本批尚不生成实际届次卡片；入库后仍为草稿，不自动接通AI问答。

当前为本机开发版。邮箱使用开发控制台，AI 默认关闭，尚未公网部署。项目招募线索与快讯暂由公共 JSON 维护；完整在线编辑和 AI 助手尚未实现。实际验证与 GitHub 同步状态以[团队进度](docs/progress.md)为准。

目录范围不等于全部官网均采集成功，也不等于已发布 255 条赛事。来源、实际结果及待处理项见[采集覆盖表](docs/competition-catalog-coverage.md)。前台默认展示未明确截止的赛事，可切换历史；时间未知不代表正在报名。

## 目录

```text
Chuangxiang-Community/
├── frontend/       # 页面、组件、浏览器请求
├── backend/        # 接口、业务、数据库模型、采集与 AI 服务
├── docs/           # 接口约定、团队进度、开发说明
├── deploy/         # 部署和定时运行脚本
├── compose.yaml    # 部署配置，本机入门暂不用
└── README.md       # 阅读入口
```

这些后端业务目录属于同一个 Django 服务。完整模块说明见[后端目录](backend/README.md)，页面对应关系见[前端说明](frontend/README.md)。

## 本地启动

### macOS 双击启动

首次使用先按[后端开发说明](docs/backend-development.md)准备 Python 3.13、PostgreSQL 17、`backend/.venv`、`backend/.env` 和数据库迁移；前端需要符合 `frontend/package.json` 要求的 Node.js。之后在 Finder 双击仓库根目录的 [`start-macos.command`](start-macos.command)。启动器会检查数据库，启动 Django 和 Vite，等两个服务就绪后用默认浏览器打开 <http://localhost:5173/>。前端依赖缺失时会按锁文件执行 `npm ci`；窗口保持打开，按 `Ctrl+C` 停止本次启动的前后端服务。若已有后端服务，启动器会复用它，不会在退出时关闭它；PostgreSQL 由本机服务或 Postgres.app 管理，退出启动器不会关闭数据库。

Windows 的 `start-frontend.bat` 保留；下方是 Windows PowerShell 的手动启动命令，仍可用于排障。

首次使用先按[后端开发说明](docs/backend-development.md)安装依赖、启动 PostgreSQL 并配置自己的 `.env`。以下命令在已配置好的项目根目录执行，两个终端分别启动：

```powershell
# 终端一：后端
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py init_competition_catalog
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

```powershell
# 终端二：前端；首次安装或依赖锁文件变化后执行 npm ci
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

打开 <http://localhost:5173/>；管理后台为 <http://127.0.0.1:8000/admin/>，没有预设管理员密码。终端保持运行；使用学生账号时保持同一个前端地址，避免来回切换 `localhost` 与 `127.0.0.1`。

## 继续开发

- 后端先读 `competitions/` 的路由、视图、序列化与模型，再进入组队业务；[代码导读](docs/code-guide.md)给出逐个文件的阅读顺序。
- 后续 AI 使用[内部信息检索](docs/information-library.md)和[模型调用服务](docs/ai-services.md)。当前普通赛事页面直接读取已保存数据，不等待采集或模型生成。
- 模型变更保留迁移，现有测试继续维护。安装依赖以各自依赖文件为准；部署见[部署说明](docs/deployment.md)。
- `.env`、`.venv/`、`.local/`、`node_modules/`、数据库备份、学生资料及密钥留在本机。共享 `editorial.json` 会进入前端，只能放公开内容。
- 官方通知是信息依据。项目许可证待团队确认，第三方代码、模型和素材需保留来源及许可说明。
