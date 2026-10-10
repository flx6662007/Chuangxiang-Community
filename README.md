# 创享社区

创享社区是面向学生的科创信息与组队平台，集中提供赛事通知、科研机会和学习资料，帮助同学找到感兴趣的方向和合适的队友。

## 主要功能

- **信息中心**：浏览赛事通知、报名信息和科研机会。
- **资源中心**：查阅学习资料，查看关联赛事与官方来源。
- **组队广场**：发布招募、申请入队、管理队伍和成员。
- **智能助手**：检索资料、分析参赛条件、查找队友，支持多轮问答。
- **账号与反馈**：学校邮箱注册、站内通知、举报和申诉。

## 技术栈

前端：Vue 3、Vite、JavaScript。后端：Django、Django REST Framework。数据库：PostgreSQL。

## 项目结构

```text
frontend/       前端页面与组件
backend/        后端接口、业务逻辑、模型与迁移
docs/           开发文档与资料包
scripts/        启动、维护与评测脚本
deploy/         部署配置
deliverables/   交付资料
```

## 本地开发

准备 Python 3.13、PostgreSQL 17 和符合 [package.json](frontend/package.json) 要求的 Node.js。按[后端开发说明](docs/backend-development.md)安装依赖、配置 `backend/.env` 并初始化数据库，再在 `frontend/` 执行 `npm ci`。

Windows 在仓库根目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

网站地址：<http://127.0.0.1:5173/>，管理后台：<http://127.0.0.1:8000/admin/>。

macOS / Linux 的启动步骤，以及端口、日志和停止服务的方法，见[后端开发说明](docs/backend-development.md)与[前端说明](frontend/README.md)。

## 文档

- [代码导读](docs/code-guide.md)：了解模块分工和请求流程。
- [接口说明](docs/api.md)：前后端对接约定。
- [资料维护](docs/competition-search-handoff.md)：赛事资料导入与检索索引。
- [智能助手](docs/ai-v3.md)：模型、检索和联网搜索配置。
- [内测使用](docs/private-beta.md) · [部署说明](docs/deployment.md)。
- [Windows 评审包](docs/portable-review.md)：解压后双击运行，附构建方法。
- [团队进度](docs/progress.md) · [完整文档目录](docs/README.md)。
