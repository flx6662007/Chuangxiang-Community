# 创享平台 · Chuangxiang Community

当前前端已连接赛事目录、学习资源、知识正文、科研和快讯接口，界面统一使用霞鹜文楷 GB。拉取本轮代码后需执行数据库迁移；启动与接口说明见 [团队进度](docs/progress.md) 和 [资料库接口](docs/api-library.md)。

面向学生的科创信息与参赛组队网站。前端使用 Vue，后端使用 Django / DRF，数据库使用 PostgreSQL。

## 先从这里看

| 想了解什么 | 入口 |
| --- | --- |
| 第一次读代码，从哪个文件开始 | **[代码导读](docs/code-guide.md)** |
| 目前完成了什么、是否已上传 | [团队进度](docs/progress.md) |
| 怎么安装和启动 | [后端开发](docs/backend-development.md) · [前端开发](frontend/README.md) |
| 前后端怎么对接 | [赛事与账号 API](docs/api.md) · [组队 API](docs/api-teams.md) |
| 查赛事资料与学习资源 | [人工赛事资料](docs/competition-research/README.md) · [目录 1—89](docs/competition-research/tongji-2026-001-089/README.md) |
| 赛事知识系统第一版交付 | [三个交付包](deliverables/competition-knowledge-v1/README.md) · [接入说明](docs/competition-delivery.md) |
| 查其他说明 | [文档导航](docs/README.md) |

## 目前能做什么

- **信息中心**：赛事列表、搜索、详情；科研板块标注“暂不开放”，首页保留人工快讯。
- **参赛组队**：发布招募、申请、双方确认入队和成员管理。
- **账号与反馈**：学校邮箱账号、站内通知、登录用户的举报与申诉。
- **管理与采集**：按学校 2026 版目录监测 255 项全学科赛事，保存官网原文与 PDF/DOCX 附件；规则提取字段并核验上架，缺项和冲突留在后台。AIC、NCDA 保留专用采集，具体流程见[赛事提取与上架](docs/catalog-publication.md)。

赛事知识、学习资源和组队目标统一使用[新版资料导入与检索](docs/competition-search-handoff.md)。执行数据库迁移和统一导入后，即可在资源中心查阅资料、在现有组队入口发布招募。

当前为本机开发版。邮箱使用开发控制台，尚未公网部署。首页赛事助手的条件理解、统一检索、带来源的 AI 回答和现有招募查询见 [赛事助手接入](docs/ai-assistant-handoff.md)；队长按接入说明配置后端 Key 并验证部署环境。内部 AI 草稿服务默认关闭。科研资料使用独立导入命令，公开展示默认关闭；快讯由内容文件维护。实际验证与 GitHub 同步状态以[团队进度](docs/progress.md)为准。

目录范围不等于全部官网均采集成功，也不等于已发布 255 条赛事。来源、实际结果及待处理项见[采集覆盖表](docs/competition-catalog-coverage.md)。前台默认展示未明确截止的赛事，可切换历史；时间未知不代表正在报名。

## 目录

```text
项目根目录（名称可自行更改）/
├── frontend/       # 页面、组件、浏览器请求
├── backend/        # 接口、业务、数据库模型、采集与 AI 服务
├── docs/           # 接口约定、团队进度、开发说明
├── deploy/         # 部署和定时运行脚本
├── compose.yaml    # 部署配置，本机入门暂不用
└── README.md       # 阅读入口
```

这些后端业务目录属于同一个 Django 服务。完整模块说明见[后端目录](backend/README.md)，页面对应关系见[前端说明](frontend/README.md)。

## 本地启动

### macOS：双击打开界面预览

首次使用先安装符合 [`frontend/package.json`](frontend/package.json) 要求的 Node.js，并在 `frontend/` 执行一次 `npm ci`。之后在 Finder 双击项目根目录的 [`打开界面预览.command`](打开界面预览.command)。脚本按自身位置寻找前端文件夹，启动或复用本项目的 Vite 服务，并打开 <http://127.0.0.1:5174/?ui_preview=1>。新启动的服务需要保持终端窗口打开，按 `Ctrl+C` 停止。

该入口用于查看当前首页界面；首页赛事和招募卡片是视觉示例。它不启动 Django 或 PostgreSQL，也不用于检验账号、赛事和组队等实际业务。

### 完整业务：手动启动

先按[后端开发说明](docs/backend-development.md)准备 Python 3.13、PostgreSQL 17、`backend/.venv`、`backend/.env` 和数据库。macOS 下从项目根目录打开两个终端，分别执行：

```bash
# 终端一：后端；首次配置或新增迁移后执行 migrate
cd backend
./.venv/bin/python manage.py migrate --noinput
./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

```bash
# 终端二：前端；首次安装或锁文件变化后执行 npm ci
cd frontend
npm ci
npm run dev
```

首次配置后端时还需按[后端开发说明](docs/backend-development.md)执行 `init_competition_catalog`，导入赛事目录。Windows PowerShell 下也可从项目根目录分别手动启动：

```powershell
# 终端一：后端
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

```powershell
# 终端二：前端；首次安装或锁文件变化后执行 npm ci
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

完整业务页面打开 <http://localhost:5173/>；管理后台为 <http://127.0.0.1:8000/admin/>，没有预设管理员密码。两个终端都需保持运行；使用学生账号时保持同一个前端地址，避免来回切换 `localhost` 与 `127.0.0.1`。

## 继续开发

- 后端先读 `competitions/` 的路由、视图、序列化与模型，再进入组队业务；[代码导读](docs/code-guide.md)给出逐个文件的阅读顺序。
- 后续 AI 使用[内部信息检索](docs/information-library.md)和[模型调用服务](docs/ai-services.md)。当前普通赛事页面直接读取已保存数据，不等待采集或模型生成。
- 模型变更保留迁移，现有测试继续维护。安装依赖以各自依赖文件为准；部署见[部署说明](docs/deployment.md)。
- `.env`、`.venv/`、`.local/`、`node_modules/`、数据库备份、学生资料及密钥留在本机。共享 `editorial.json` 会进入前端，只能放公开内容。
- 官方通知是信息依据。项目许可证待团队确认，第三方代码、模型和素材需保留来源及许可说明。

目录90—130的赛事资料、学习导读与草稿入库，见[本轮交付说明](docs/curated-research-90-130.md)。资料包含实际届次、来源、缺口和原始附件；与1—89及131—255分工包分别维护。
