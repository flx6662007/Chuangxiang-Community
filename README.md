# 创享社区

面向学生的科创信息与参赛组队网站。前端使用 Vue 3 / Vite，后端使用 Django / DRF，数据库使用 PostgreSQL。

## 功能

- **赛事与学习资源**：赛事目录、届次通知、报名与组队状态、资料正文、来源和关联学习资源。
- **组队与账号**：学校邮箱账号、招募发布、申请与双方确认、成员管理、站内通知、举报和申诉。
- **科研与快讯**：科研介绍、招募筛选、详情及来源链接；首页快讯由团队手动维护。
- **AI 助手**：赛事、科研、资源和智能四种模式；关键词与 BGE 混合检索、带来源回答、多轮问答、流式输出；赛事向导连接分析与找队友流程。可按配置启用联网搜索。

上述为代码能力。科研公开展示、模型回答、语义索引、真实邮件和联网搜索分别需要配置；克隆仓库不会复制数据库、账号、密钥、模型或正在运行的内测环境。实际接续入口见[当前进度](docs/progress.md)。

## 阅读入口

| 要做什么 | 文档 |
| --- | --- |
| 第一次读代码 | [代码导读](docs/code-guide.md) · [后端模块](backend/README.md) · [前端页面](frontend/README.md) |
| 安装和启动 | [后端开发](docs/backend-development.md) · [前端开发](frontend/README.md) |
| 使用内测或部署 | [邀请内测](docs/private-beta.md) · [部署说明](docs/deployment.md) |
| 接续 AI | [AI 接入](docs/ai-v3.md) · [多轮与联网更新](docs/ai-optimization-20261008.md) · [赛事向导](docs/ai-assistant-handoff.md) |
| 更新赛事及资源 | [统一资料与检索](docs/competition-search-handoff.md) · [资料库 API](docs/api-library.md) |
| 导入科研资料 | [科研交付与配置](docs/releases/research-ai-20261007.md) |
| 查接口和其他资料 | [文档导航](docs/README.md) |

## 目录

```text
Chuangxiang-Community/
├── frontend/       # 页面、组件、浏览器请求和前端测试
├── backend/        # 接口、业务、模型、迁移、AI 和后端测试
├── docs/           # 当前文档、接口、资料包和来源
│   └── archive/    # 早期方案、阶段验收与历史进度
├── scripts/        # 开发/内测启停、资料构建、索引准备和评测
├── deploy/         # 部署、定时任务和可选搜索服务配置
├── deliverables/   # 正式交付包，保留清单与校验数据
├── compose.yaml    # 容器部署配置
├── AGENTS.md       # 仓库操作规则
└── agent.md        # 接续开发约定
```

后端业务目录属于同一个 Django 工程；数据库模型和迁移随对应应用维护。文档内的正式资料包与来源快照是导入、重建和核对依据，不按重复文件或生成物批量清理。

## 本地启动

### 首次准备

1. 安装 Python 3.13、PostgreSQL 17，以及符合 [package.json](frontend/package.json) 要求的 Node.js。
2. 按[后端开发](docs/backend-development.md)创建 `backend/.venv`、安装依赖、配置自己的 `backend/.env` 和开发数据库，执行已有迁移。
3. 在 `frontend/` 执行 `npm ci`。先启动空工程时，列表为空是正常状态；赛事与科研内容按各自交接文档导入。
4. 需要 AI 时按 [AI 接入](docs/ai-v3.md)配置服务端密钥、模型目录和索引；普通页面读取已保存内容，不等待模型生成。

### Windows

完成首次准备后，在仓库根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

默认前端为 <http://127.0.0.1:5173/>，后端为 <http://127.0.0.1:8000/>。脚本隐藏启动两个进程；日志在 `.local/dev/`。Node 不在 PATH 时可指定 `-NodePath 'C:/Program Files/nodejs/node.exe'`。查看和停止：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action status
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action stop
```

端口占用时按[后端开发](docs/backend-development.md)指定另一组端口，启停时使用同一组参数。脚本不安装依赖、不改数据库；Python 修改后重启后端。

### macOS / Linux

分别在两个终端执行：

```bash
# 终端一，从仓库根目录开始；先完成依赖、配置和迁移
cd backend
./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

```bash
# 终端二，从仓库根目录开始
cd frontend
npm run dev
```

管理后台为 <http://127.0.0.1:8000/admin/>，管理员由各自创建。登录与验证时固定使用同一个前端主机名，避免切换 `localhost` / `127.0.0.1`。

macOS 仅看界面时，可在安装前端依赖后双击[打开界面预览.command](打开界面预览.command)。该入口使用 UI 示例，不启动数据库或后端，不用于业务验收。

## 配置与维护

- `.env.example` 可共享；真实 `.env`、账号口令、数据库备份、日志、模型与索引留在本机。
- `DEEPSEEK_*` 控制聊天和赛事向导；`AI_ENABLED` 控制独立的内部草稿服务，不能混用。
- `PUBLIC_RESEARCH_ENABLED=1` 才开放科研数据；还需导入资料。联网搜索另见 [SearXNG 配置](docs/ai-optimization-20261008.md)。
- 邮件默认输出到开发终端；真实注册需配置发件服务。内测账号和入口验证见[邀请内测](docs/private-beta.md)。
- 资料维护以人工整理和导入为主，历史采集代码及维护命令保留。迁移、依赖锁文件、测试和第三方许可说明随代码保存。
- 项目许可证待团队确认；第三方代码、模型和素材沿用各自许可。

校验与测试命令见[后端开发](docs/backend-development.md)和[前端说明](frontend/README.md)。整理范围及本轮验证见[工程整理记录](docs/engineering-cleanup-20261008.md)。
