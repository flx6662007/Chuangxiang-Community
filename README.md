# 创享平台 · Chuangxiang Community

创新俱乐部发起的科创资讯与参赛组队网站。通过集中展示赛事、保留原文来源、固定模板招募，改善微信群中信息难查找、招募分散和邀请新成员不便的问题。

**当前开发版支持真实赛事浏览、完整参赛组队、登录举报与申诉。** AIC、数维杯、NCDA 三个官方来源接入自动采集；首页预留人工快讯，展示已核查的本科科研线索。卡片读取已保存数据，打开页面不等待爬虫或 AI。开发邮件输出到终端；AI 默认关闭；尚未公网部署。

账号与数据基线来自 [PR #3](https://github.com/flx6662007/Chuangxiang-Community/pull/3)，蓝白界面来自 [PR #4](https://github.com/flx6662007/Chuangxiang-Community/pull/4)。本次组队、采集的验证与 GitHub 同步状态见 [团队进度](docs/progress.md)。代码合入不代表已经公网部署。

## 从这里开始

| 需要了解 | 入口 |
| --- | --- |
| 目前做到哪里、还有什么 | [团队进度](docs/progress.md) |
| 怎么启动 | [后端开发](docs/backend-development.md) · [前端开发](frontend/README.md) |
| 代码在哪里、各文件做什么 | [后端目录](backend/README.md) · [前端实现](docs/frontend-implementation.md) |
| 前后端怎么对接 | [赛事与账号 API](docs/api.md) · [组队 API](docs/api-teams.md) · [举报申诉 API](docs/api-governance.md) |
| 其他设计、字段、来源和验收 | [文档导航](docs/README.md) |

## 已实现功能

| 部分 | 当前能力 | 边界 |
| --- | --- | --- |
| 赛事页面 | 列表、搜索、分页、分类、完整详情、来源链接与关联组队入口 | 读取已保存数据，不在访问时采集或生成卡片；官方未知字段明确显示为空缺 |
| 内容后台 | 草稿、来源核验、发布、下架与审计；采集记录和候选采纳 | 赛事下架会结束未完成申请并收回联系权限，保留已加入的成员关系 |
| 账号页面 | 学校邮箱注册、登录、退出、验证码核验、联系方式维护、密码找回 | 仅接受 `@tongji.edu.cn`；控制台邮件仅供开发；未开放邮箱自助换绑 |
| 参赛组队 | 固定模板发布／编辑、申请／接受联系、双方确认、版本变更后继续、退出／移除／解散、站内通知 | 新增发布和申请须核验邮箱与资料；接受申请不占名额，双方确认才入队；联系方式只给获授权双方 |
| 赛事采集 | 三个官方站点适配器、原文版本、去重、候选、失败记录与定时任务 | 报名和投稿分开；重要字段变化留待复核；新增站点需要适配规则，详见[来源清单](docs/competition-sources.md) |
| 举报与申诉 | 赛事／招募详情举报、本人记录与反馈、本人事项申诉、后台独立复核 | 当前登录即可使用；被限制用户仍可申诉；举报不自动处罚，复核结论不等同于撤销处分 |
| 快讯与本科科研 | 手动快讯位置、6 条官方明确接受本科生的科研线索及原文链接 | 维护 `frontend/src/data/editorial.js`；快讯当前为空；旧招募不代表当前有名额，见[内容维护](docs/undergraduate-labs.md) |
| 数据模型 | 用户、赛事、组队、科研、资源、快讯、通知、收藏、治理与采集追溯模型及迁移 | 模型存在不等于相应页面和业务流程完成 |
| AI 服务包 | 通知提取、快讯草稿、来源依据校验、错误分类及离线测试 | 默认关闭；没有真实模型联调、HTTP 入口或自动发布 |

## 本地运行

新电脑先按 [后端开发说明](docs/backend-development.md) 安装 Python、PostgreSQL，填写自己的 `.env`，安装依赖并执行迁移。前端需要符合 `frontend/package.json` 要求的 Node.js 和 npm。不要重复执行 `startproject` 或 `startapp`。

已配置好的电脑，拉取更新后先执行已有迁移，再打开前后端：

```powershell
# 终端一：后端
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate
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
│   ├── teams/                  # 招募、申请、成员事务、API 与到期结算
│   ├── research/               # 科研机会模型
│   ├── resources/              # 外链资源与版本模型
│   ├── newsletters/            # 快讯与内容项模型
│   ├── favorites/              # 收藏模型
│   ├── notifications/          # 事务事件、站内通知与本人已读接口
│   ├── governance/             # 登录举报、本人申诉、管理员独立复核与留痕
│   ├── ingestion/              # 官方适配器、采集命令、原文版本与候选采纳
│   ├── common/                 # 共用模型校验
│   ├── ai_services/            # 后端内部模型调用服务
│   ├── templates/account/email/ # 验证码与找回密码邮件模板
│   ├── scripts/                # 数据库等辅助检查
│   ├── .env.example            # 配置样例，无真实密钥
│   ├── requirements.txt        # 本地通用依赖
│   └── requirements-production.txt # 正式部署补充依赖
├── deploy/                     # Linux 部署配置及 Windows 本机定时脚本
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
| HTTPX、Beautiful Soup | 有限来源的 HTTP 获取和 HTML 正文解析；不需要付费模型 |
| `ai_services` | 模型内部调用、提示词与校验，默认关闭 |
| Linux、Docker Compose、Caddy、Gunicorn、Redis、SMTP | 已提供部署准备文件；尚未在目标服务器运行或验证真实发信 |

Python 精确版本以依赖文件为准，前端依赖以 `package-lock.json` 为准。本地开发不需要先安装 Docker、Redis 或购买邮件服务。Windows 定时采集依赖本机持续开机、用户登录与 PostgreSQL 可连接；真实 AI 和公网部署另行接续。

## AI 开发入口

- `extract_notice(source_text, source_url)`：提取通知字段，保留原文依据与缺失项。
- `generate_newsletter(items)`：用调用方选定的已核实资讯生成草稿，保留来源引用。

两个函数供后端内部调用，前端不能直接访问。当前 `AI_ENABLED=0`；真实调用需要服务端兼容 API 地址、模型名与密钥。Qwen 是待评测候选，尚未确定最终模型。密钥只留在服务端，不能提交 Git 或放入前端。

结构和引文检查不能保证内容完全正确，生成结果仍需管理员确认。赛事卡片的样式提前写在前端，打开页面只读取已保存数据，不等待 AI 制作卡片。详细边界见 [AI 服务说明](docs/ai-services.md)。

## 数据与许可

旧开发样例可用 `retire_demo_data --actor-id 管理员编号` 下架并保留历史；正常内部演示使用官方采集数据。采集保留原文链接，官方通知仍是最终依据。项目许可证尚待团队确认；引入第三方代码、模型和素材应记录来源、版本及许可证。仓库不提交真实学生资料、数据库备份、密码或服务密钥。
