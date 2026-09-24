# 创享平台 · Chuangxiang Community

国豪书院创新俱乐部发起的科创资讯与参赛组队网站。面向本校学生集中展示赛事、科研机会和快讯，通过固定模板发布招募，改善微信群中信息难查找、招募分散和邀请新成员不便的问题。

**当前仓库用于共同开发，已有后端工程骨架，尚未形成完整可用的网站。** 模块目录存在不代表功能已经完成；`competitions/` 是赛事代码模块，没有采集或导入赛事数据。

## 文档入口

| 文档 | 查看内容 |
| --- | --- |
| [团队进度](docs/progress.md) | 当前交付、下一步、依赖和验收点；进度统一在此更新 |
| [产品范围](docs/product-scope.md) | 功能边界、组队规则与 AI 方向 |
| [后端开发说明](docs/backend-development.md) | 首次配置、日常启动、检查与迁移说明 |
| [API 说明](docs/api.md) | 已实现接口，以及尚未确定的业务接口 |
| [前端说明](frontend/README.md) | 前端目录的当前用途与开发入口 |

## 项目结构

```text
Chuangxiang-Community/
├── frontend/                   # 前端代码位置，当前状态见目录说明
├── backend/
│   ├── manage.py               # Django 管理命令入口
│   ├── config/                 # 配置、网址路由和健康检查
│   ├── accounts/               # 账号模块；含首次迁移保护
│   ├── competitions/           # 赛事模块；模型和接口待开发
│   ├── scripts/                # 数据库检查等辅助脚本
│   ├── .env.example            # 本地配置样例
│   └── requirements.txt        # Python 依赖版本
├── docs/                       # 共享进度、接口和开发说明
├── .gitignore
└── README.md
```

`accounts` 和 `competitions` 属于同一个 Django 后端，不需要分别部署。模型和迁移文件需要提交；`.venv/`、`.env`、`.local/` 和本地数据库数据不提交。

## 本地运行

新电脑先按 [后端开发说明](docs/backend-development.md) 获取正确分支、安装依赖、准备 PostgreSQL 并填写 `.env`。骨架尚未合入 `main` 时，新克隆的仓库需切换到 `codex/backend-bootstrap`；合并完成后直接使用 `main`。

已配置好的 Windows 电脑，在仓库根目录执行：

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

如果终端已经位于 `backend`，只执行第二行。访问 <http://127.0.0.1:8000/api/v1/health/> 应收到：

```json
{"status":"ok","service":"chuangxiang-backend"}
```

这只表示健康检查接口可以响应，**不代表数据库或业务功能可用**。数据库检查和首次迁移的前置条件见开发说明；当前不要直接迁移默认用户表。

## 产品范围

以下为产品约定，具体实现状态以团队进度为准：

- 首期只做电脑端网页，在国豪书院试点，接受本校其他院系学生注册。
- 游客可查看资讯、快讯和不含联系方式的招募卡；发布与申请前须完成学校邮箱验证。
- 招募仅用于参赛，必须关联已收录赛事；采用固定模板，不设开放式讨论区或站内聊天。
- 资讯保留来源链接与更新时间；计划定期检查允许接入的官方来源，并支持手动更新。
- 快讯由管理员按需生成草稿、确认后发布；资源中心由管理员维护。
- 卡片模板由前端提前编写，页面读取已有数据，不等待 AI 制作卡片。

## 技术方案

| 状态 | 技术 | 用途 |
| --- | --- | --- |
| 已接入 | Python 3.13、Django、Django REST Framework | 后端工程和接口基础 |
| 已接入 | PostgreSQL 17、psycopg、python-dotenv | 数据库连接和本地配置加载 |
| 已接入 | Django 认证与权限配置、自带测试工具 | 基础权限配置和骨架测试；登录业务待开发 |
| 规划 | Vue 3、Vite、Vue Router、Axios、Element Plus | 前端界面、构建、路由和接口调用 |
| 业务待开发 | Django ORM、migrations、Admin | Django 已包含这些组件；平台模型、迁移和后台管理尚待实现 |
| 规划 | django-allauth | 账号与邮箱核验；尚未安装或接入 |
| 规划 | Redis、RQ、HTTPX、Beautiful Soup | 后台任务与资讯采集 |
| 规划 | drf-spectacular、pytest、pytest-django | 扩展接口文档和业务测试 |
| 规划 | Linux、Gunicorn、Nginx | 正式部署；本地开发可使用 Windows |
| 候选 | Qwen 托管 API | 通知字段提取与快讯草稿生成，需用实际样本评测 |

实际 Python 依赖以 [`backend/requirements.txt`](backend/requirements.txt) 为准，当前不必安装所有规划组件。邮件服务、Docker Compose、Pinia、TypeScript、pgvector 按后续需求决定。

AI 尚未接入。优先验证官方通知字段提取和快讯草稿生成，保留来源依据，校验后再发布。模型密钥只保存在服务端，AI 不直接决定账号权限或入队结果。

## 许可与数据

项目许可证尚待团队确认。引入第三方软件、模型和素材时记录来源、版本及许可证。仓库不提交真实学生资料、数据库备份、密码或服务密钥。
