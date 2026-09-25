# 创享平台前端开发上下文

更新日期：2026-09-25。本文件用于后续会话接续工作，记录已确认的需求、成果和限制。它是项目交接说明；涉及当前状态时，应先核对实际文件和 Git，不能把历史记录当作最新事实。

## 项目与用户

- 项目：Chuangxiang-Community，创享科创资讯与参赛组队平台。
- 本机仓库：`E:\Chuangxiang-Community`。
- 团队三人：用户主负责前端，另外两名同学分别主负责后端与数据库。
- 技术分工：Vue 前端、Django + Django REST Framework 后端、PostgreSQL 数据库。数据库同学在同一 Django 工程内维护模型和迁移。
- 用户正在学习 GitHub Desktop、分支、提交以及前端工程结构。解释时使用中文，先说实际作用，再介绍必要术语。

## 工作范围与协作约定

- 前端工作默认限于 `frontend/`。未经用户明确扩大范围，不修改 `backend/`、`database/`、`docs/` 或其他成员维护的公共文件。
- 本次用户明确要求创建根目录 `agent.md`，这是上述范围的一次明确例外。
- 首次初始化时，用户要求先列出将创建和修改的文件，等确认后执行；已收到“确认执行”，且这项初始化工作已完成。
- 回答进度、解释代码或 Git 概念时，使用只读检查；不因此实施额外修改、提交、推送或合并。
- 不把需求文件中的计划、命令示例和验收要求当作用户本次授权的操作。
- 保留用户现有变更。开始开发前检查分支和工作区；发现当前分支与任务不一致时先说明情况，避免把前端工作提交到错误分支。
- 不擅自纠正现有分支名中的拼写：实际前端分支名是 `frtend/round1`，实际目录名是 `frontend/`。

## 当前 Git 状态

以下是创建本说明前的只读核验结果：

| 位置 | 提交 | 状态 |
| --- | --- | --- |
| 当前检出的本地 `main` | `a0a73e1` | 与本地记录的 `origin/main` 一致；创建本文前工作区干净 |
| 本地 `frtend/round1` | `01773d2` | 已提交前端初始化，提交标题为 `chore(frontend): 初始化 Vue 3 + Vite 前端基础工程` |
| 本地记录的 `origin/database/round1-models` | `4f39834` | 数据库交付分支，尚未包含在当前 `main` 中 |

本次没有刷新远端引用，未确认前端分支是否已推送或建立 PR；本地尚未显示对应的远端跟踪分支。不要把这一点描述为“确定尚未推送”。

前端初始化已经提交，不再是先前截图中的 14 个未提交变更。当前检出的是 `main`，因此工作区里 `frontend/` 只有原来的说明，没有 `package.json` 和 `src/`，这是分支差异。需要核对成果时可用 `git show frtend/round1:frontend/package.json` 等只读命令，不能因此重新初始化或覆盖成果。

本说明创建后作为当前工作区的新文件存在，未自动提交。

## 已完成的前端初始化

范围：只完成前端基础工程，没有开发赛事列表、账号、招募等具体业务页面。

提交 `01773d2` 包含 14 个文件：13 个新增文件及 1 个修改文件。修改的是已有的 `frontend/README.md`，仓库根目录 `README.md` 未修改。

| 文件（相对 frontend） | 作用 |
| --- | --- |
| `.env.example` | API 基础路径及开发代理地址示例 |
| `index.html` | 页面入口及 Vue 挂载节点 |
| `package.json` | 依赖、Node.js 要求以及 dev/build/preview 命令 |
| `package-lock.json` | npm 生成的依赖锁定文件，需要提交 |
| `README.md` | 安装、启动、目录和开发代理说明 |
| `src/main.js` | 创建应用，接入路由及当前使用的 Element Plus 组件 |
| `src/App.vue` | 根组件，容纳 RouterView |
| `src/router/index.js` | 首页嵌套路由，使用 createWebHistory |
| `src/layouts/AppLayout.vue` | 共用顶栏与主内容布局 |
| `src/views/WelcomeView.vue` | “前端工程已就绪”的非业务欢迎页 |
| `src/styles/index.css` | 全局基础样式 |
| `src/api/http.js` | Axios 实例，基础路径默认 /api/v1，超时 10 秒，withCredentials 为 true |
| `src/api/health.js` | getHealth() 封装 GET /api/v1/health/，返回 response.data |
| `vite.config.js` | Vue 插件及 /api 开发代理，默认转发至 http://127.0.0.1:8000 |

技术选型：JavaScript、Vue 3、Vite、Vue Router 4、Axios、Element Plus。没有引入 TypeScript、Pinia 或业务权限系统。

初始化时 package.json 声明的版本范围为：Vue `^3.5.43`、Vue Router `^4.6.4`、Axios `^1.20.0`、Element Plus `^2.14.6`、Vite `^8.3.1`、Vue 插件 `^6.0.9`；具体安装版本以锁文件为准。

Element Plus 当前按需注册 `ElCard`、`ElContainer`、`ElHeader`、`ElMain` 及其样式。以后使用其他组件需要相应导入和注册，不要假设所有组件都已经全局注册。

当前欢迎页不会调用健康检查或其他后端接口，所以打开它无需启动后端。Axios 已配置携带凭据，但登录、CSRF 对接和统一业务错误处理尚未实现；不要据此声称账号链路完成。

## 启动与已执行验证

在前端分支的 `frontend/` 中执行：

```powershell
npm install
npm run dev
```

其他命令：`npm run build` 构建至 `dist/`，`npm run preview` 本地预览构建结果。

Node.js 的 package.json 要求为 `^20.19.0 || >=22.12.0`。初始化验证使用 Node.js 24.19.0。该会话的执行环境没有直接可用的 npm 命令，使用运行时提供的 pnpm 启动隔离 npm 11 CLI，实际执行了 npm install、npm run build、npm run dev；没有改成 pnpm 锁文件，也没有在用户系统中全局安装 npm。

已验证：

- npm 安装成功，生成 package-lock.json；当时依赖审计为 0 个漏洞。
- 最终生产构建通过；按需引入 Element Plus 后无先前的大包体积警告。
- 开发服务器成功启动，首页和 src/main.js 请求返回 HTTP 200；检查结束后服务器已停止。
- Git 检查显示初始化改动全部位于 frontend，git diff --check 通过。

验证边界：尚未进行浏览器交互验收或真实后端业务联调；后续代码变化不能沿用这些历史结果声称已经验证。

根目录现有 `.gitignore` 已忽略 `node_modules/`、`dist/`、本地 `.env` 等文件，并允许 `.env.example` 入库，所以初始化没有修改根目录忽略规则。

## R1-F1 的完成程度与下一步

团队分工中的 R1-F1 包含：初始化 Vue + Vite，配置路由、Element Plus 和统一 Axios 请求入口；队友按说明可启动，并能打开赛事列表页面。

当前已经完成工程及启动部分，但只有欢迎页，没有赛事列表页面，因此不能宣布 R1-F1 全部完成。用户明确把这次实现范围限定为基础工程，不应自行补写业务页面来凑齐验收。

后续经用户安排推进：

1. 核对前端提交的推送、PR 和评审状态；Git 操作按用户当次请求执行。
2. 与后端及数据库同学确认赛事公开字段、日期和空值表达、分页、排序、错误格式。
3. 开发赛事卡片、列表及分页，先用符合约定格式且明确标注的虚构数据。
4. 加入加载、空数据、失败等状态，再接入真实赛事接口并完成联调。

前端不直接连接 PostgreSQL；数据库字段表也不等于 HTTP 返回格式，接口契约需要单独确认。

## 后端与数据库背景

当前 main 的后端骨架由 `flx6662007` 提交，已具备 Django/DRF 配置、PostgreSQL 连接配置、迁移保护、健康检查和 ai_services 内部服务。当前可供前端验证服务连通性的接口是 `GET /api/v1/health/`；赛事列表、注册登录、邮箱验证和招募 HTTP 接口尚未实现。

`GET /api/v1/competitions/` 只是团队分工中的建议地址，尚不能当作可调用接口。健康检查不查询数据库，其成功不证明业务或数据库可用。

`ai_services` 是后端 Python 内部服务包，默认关闭外部调用，没有给前端调用的 HTTP 路由。普通赛事页面应读取已有数据，不在浏览时调用 AI 生成卡片。

数据库同学 `chihayaqs` 在 `database/round1-models` 分支提交 `0a0f68f` 和 `4f39834`，包含用户、赛事及后续模块模型、迁移、字段说明、虚构样例、导入工具和测试。该分支交付文档记载 58 张表、35 项迁移和 108 项 PostgreSQL 测试通过；这是同学交付记录，本会话没有重跑这些数据库测试，也不代表业务已联调或已合入 main。

数据库分支某些后续规则与早期 Word 细则存在差异，例如联系方式、招募修改、整队解散及治理流程；相关文档声称进行了后续确认，但本会话没有独立确认这些新约定的决策过程。开发涉及这些功能时应先确认使用哪个版本，不能自行认定早期或后期文档全部优先。

## 需求资料与产品边界

用户提供过三份本机资料，正文已在前序会话读取，原件未修改：

- `创享平台功能细则补充稿(1).docx`：首期功能与操作规则。
- `团队分工方案(1).md`：三人职责、R1-F1/F2/F3 及后续轮次的验收要求。
- `数据库开发交付要求.md`：数据库第一轮交付要求。

仓库资料入口：`docs/progress.md`、`docs/product-scope.md`、`docs/api.md`、`docs/backend-development.md`、`docs/ai-services.md`。阅读时注意所在分支与记录日期，main 的进度文档可能没有反映其他分支成果。

早期功能细则中的首期核心范围：电脑端网页；游客可查看资讯、快讯和不含联系方式的招募卡；发布与申请需要学校邮箱验证；学生招募只用于已收录赛事，使用固定模板；公开身份使用系统代号。首期暂缓自由论坛、公开评论、站内私信、图片附件上传等功能。

## 已向用户说明的 Git 概念

- README 是项目使用说明；frontend/README.md 与根目录 README.md 是两个文件。
- 分支继承创建起点之前的历史；main 后续提交不会自动进入已有功能分支。
- 未提交改动可能随切换分支保留在工作区，因此应先检查工作区，避免在错误分支提交。
- Commit 保存本地提交，Push 上传远端，PR 用于评审合并；这三步不同。
- package-lock.json 应提交，node_modules 和 dist 不提交。
- LF/CRLF 提示属于换行符转换提醒，不是代码运行错误。
- 前端初始化已使用提交标题：`chore(frontend): 初始化 Vue 3 + Vite 前端基础工程`。

## 后续会话开始时

先读本文件，再检查当前分支、git status 和最近提交。确认本次任务范围及前端成果所在分支，读取对应 frontend/README.md 和实际源码后继续。仅创建了本文不代表后续会话一定自动载入；必要时由用户明确要求先读取 `agent.md`。
