# 创享平台 · Chuangxiang Community

国豪书院创新俱乐部发起的科创资讯与参赛组队网站。通过集中展示赛事、保留原文来源、固定模板招募，改善微信群中信息难查找、招募分散和邀请新成员不便的问题。

**当前提供无需购买服务的本地开发版：赛事列表、详情、后台维护和学校邮箱账号流程已实现；组队业务尚未开放。** 当前赛事数据是明确标记的虚构样例，没有采集真实赛事。开发邮件输出到后端终端，不会投递到真实邮箱；AI 默认关闭；尚未公网部署。

两轮成果已通过 [PR #3](https://github.com/flx6662007/Chuangxiang-Community/pull/3) 合入 `main`，全队可从主分支获取共同开发基线。验证结果与后续任务见 [团队进度](docs/progress.md)。代码合入不代表已经公网部署。

## 文档入口

| 文档 | 内容 |
| --- | --- |
| [团队进度](docs/progress.md) | 两轮交付、验证边界、后续分工与 Git 状态 |
| [后端开发](docs/backend-development.md) · [前端开发](frontend/README.md) | 首次配置、迁移和日常启动 |
| [人工验收](docs/manual-checks.md) | 按页面检查赛事、账号、验证码与后台 |
| [API 说明](docs/api.md) | 实际路径、参数、返回字段和错误处理 |
| [数据库交付](docs/database-handoff.md) · [字段规则](docs/database-fields.md) | 模型基线、约束、样例与接续写入要求 |
| [用户字段](docs/user-fields-table.md) · [赛事字段](docs/competition-fields-table.md) · [其他字段](docs/remaining-fields-table.md) | 各业务模型的数据定义 |
| [产品范围](docs/product-scope.md) | 产品规划；具体实现状态以团队进度为准 |
| [AI 服务](docs/ai-services.md) | 模型调用、提示词、结果校验与异常处理 |
| [部署准备](docs/deployment.md) · [资源与费用清单](docs/procurement.md) | 后续开放访问需要的资源、部署步骤和采购时机 |

## 已实现功能

| 部分 | 当前能力 | 边界 |
| --- | --- | --- |
| 赛事页面 | 公开赛事列表、搜索、分页、详情与来源链接；加载、空结果和失败提示 | 页面读取数据库，不在访问时采集或生成卡片；分类筛选已提供 API，页面暂无分类控件 |
| 内容后台 | 草稿维护、分类标签、来源核验、发布、填写理由下架及操作记录 | 关联队伍的赛事暂不能下架，需先接续队伍状态处理；未建立自动采集任务 |
| 账号页面 | 学校邮箱注册、登录、退出、验证码核验、联系方式维护、密码找回 | 仅接受 `@tongji.edu.cn`；控制台邮件仅供开发；未开放邮箱自助换绑 |
| 业务资格 | 服务端检查账号状态、当前邮箱核验、有效限制和联系方式 | 已提供可复用权限基础；招募、申请、入队接口尚未实现 |
| 数据模型 | 用户、赛事、组队、科研、资源、快讯、通知、收藏、治理与采集追溯模型及迁移 | 模型存在不等于相应页面和业务流程完成 |
| AI 服务包 | 通知提取、快讯草稿、来源依据校验、错误分类及离线测试 | 默认关闭；没有真实模型联调、HTTP 入口或自动发布 |

## 本地运行

新电脑先按 [后端开发说明](docs/backend-development.md) 安装 Python、PostgreSQL，填写自己的 `.env`，安装依赖并执行迁移。前端需要符合 `frontend/package.json` 要求的 Node.js 和 npm。不要重复执行 `startproject` 或 `startapp`。

已配置好的电脑，打开两个终端，分别从仓库根目录执行：

```powershell
# 终端一：后端
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

```powershell
# 终端二：前端；首次安装或锁文件变化后先执行 npm ci
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

打开 <http://localhost:5173/>。前端通过 Vite 将 `/api` 请求转给本机后端；使用账号功能时保持同一个浏览器地址，不要来回切换 `localhost` 和 `127.0.0.1`。终端需保持运行，`Ctrl+C` 停止对应服务。

后端健康检查：<http://127.0.0.1:8000/api/v1/health/>；管理后台：<http://127.0.0.1:8000/admin/>。健康检查只说明 HTTP 服务可响应，不能证明数据库、邮件或业务流程可用。管理员需在本机单独创建，没有预设管理员密码。

## 项目结构

```text
Chuangxiang-Community/
├── frontend/                   # Vue 页面、路由、接口封装与前端测试
├── backend/
│   ├── config/                 # Django 配置、根路由和测试配置
│   ├── accounts/               # 自定义用户、认证适配、本人资料、业务资格
│   ├── competitions/           # 赛事模型、查询 API、事务服务和 Admin
│   ├── teams/                  # 招募、申请、成员等模型；业务接口待开发
│   ├── research/               # 科研机会模型
│   ├── resources/              # 外链资源与版本模型
│   ├── newsletters/            # 快讯与内容项模型
│   ├── favorites/              # 收藏模型
│   ├── notifications/          # 业务事件与站内通知模型
│   ├── governance/             # 管理操作记录模型
│   ├── ingestion/              # 采集与 AI 处理追溯模型
│   ├── common/                 # 共用模型校验
│   ├── ai_services/            # 后端内部模型调用服务
│   ├── templates/account/email/ # 验证码与找回密码邮件模板
│   ├── scripts/                # 数据库等辅助检查
│   ├── .env.example            # 配置样例，无真实密钥
│   ├── requirements.txt        # 本地通用依赖
│   └── requirements-production.txt # 正式部署补充依赖
├── deploy/                     # Linux 容器与 HTTPS 配置
├── compose.yaml                # 正式部署服务编排
├── docs/                       # 共享进度、接口与开发说明
└── README.md
```

这些业务目录属于同一个 Django 后端，不需要分别购买服务器。`ai_services` 是 Python 服务包，不创建数据库表，也不单独部署。GitHub 同步代码、迁移和文档；`.venv/`、`.env`、`.local/`、`node_modules/`、数据库记录及真实凭据不提交。

## 技术方案

| 技术 | 用途与当前状态 |
| --- | --- |
| Python 3.13、Django 5.2、DRF | 后端业务、管理后台和 JSON API，已接入 |
| PostgreSQL 17、Django ORM、psycopg | 数据持久化、迁移、约束与事务，已接入 |
| django-allauth Headless、Session、CSRF | 学校邮箱账号、验证码和浏览器会话，已接入 |
| Vue 3、JavaScript、Vite、Vue Router、Axios、Element Plus | 电脑端界面及前后端请求，已接入 |
| HTTPX、`ai_services` | 兼容模型 API 的内部调用，默认关闭 |
| Linux、Docker Compose、Caddy、Gunicorn、Redis、SMTP | 已提供部署准备文件；尚未在目标服务器运行或验证真实发信 |

Python 精确版本以依赖文件为准，前端依赖以 `package-lock.json` 为准。本地免费开发不需要先安装 Docker、Redis 或购买邮件服务。采集调度、真实 AI 和组队业务在核心流程验收后接续。

## AI 开发入口

- `extract_notice(source_text, source_url)`：提取通知字段，保留原文依据与缺失项。
- `generate_newsletter(items)`：用调用方选定的已核实资讯生成草稿，保留来源引用。

两个函数供后端内部调用，前端不能直接访问。当前 `AI_ENABLED=0`；真实调用需要服务端兼容 API 地址、模型名与密钥。Qwen 是待评测候选，尚未确定最终模型。密钥只留在服务端，不能提交 Git 或放入前端。

结构和引文检查不能保证内容完全正确，生成结果仍需管理员确认。赛事卡片的样式提前写在前端，打开页面只读取已保存数据，不等待 AI 制作卡片。详细边界见 [AI 服务说明](docs/ai-services.md)。

## 数据与许可

开发样例均为虚构数据，不得当作真实通知对外发布。项目许可证尚待团队确认；引入第三方代码、模型和素材应记录来源、版本及许可证。仓库不提交真实学生资料、数据库备份、密码或服务密钥。
