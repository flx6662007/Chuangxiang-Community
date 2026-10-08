# 代码导读

先跟着“打开赛事列表”读完一次请求。掌握这一条流程后，再看资料编审、组队和 AI；不必从第一个文件开始逐个通读。本页是代码导航，环境是否已导入资料、启用科研或连接模型，需另外核验。

## 先认识几个文件名

| 文件 | 回答的问题 |
| --- | --- |
| `urls.py` | 这个网址交给谁处理？ |
| `views.py` | 请求有哪些条件，需要返回什么？ |
| `serializers.py` | 哪些数据可以发给前端，如何组织成 JSON？部分写接口也用它检查输入。 |
| `models.py` | 数据保存哪些字段，字段之间是什么关系？ |
| `services.py` | 发布、申请、入队等操作，必须按哪些业务规则执行？ |
| `admin.py` | 管理员从哪里查看或操作这些内容？ |

`views.py` 的“视图”指后端请求处理代码；浏览器里看到的页面在 `frontend/src/views/`。

## 后端第一条阅读路线

以具体届次列表的 `GET /api/v1/competitions/?search=人工智能` 为例：

| 顺序 | 打开文件 | 先看什么 |
| --- | --- | --- |
| 1 | [总路由](../backend/config/urls.py) | 找到 `api/v1/competitions/`，看它转到哪个业务路由 |
| 2 | [赛事路由](../backend/competitions/urls.py) | 空路径对应 `CompetitionListView`，编号路径对应详情 |
| 3 | [赛事视图](../backend/competitions/views.py) | 先看 `CompetitionListView.get_queryset()` 如何读取搜索和分类条件；再看 `PublicCompetitionMixin` 如何限定公开数据、排序 |
| 4 | [赛事模型](../backend/competitions/models.py) | 找到 `Competition`，对照标题、截止日期、发布状态等字段；约束可以第二遍再读 |
| 5 | [赛事序列化](../backend/competitions/serializers.py) | 看 `CompetitionListSerializer.Meta.fields`，这里决定哪些字段交给前端 |

这次查询的过程是：**路由找到处理代码 → 按条件查数据库 → 挑选公开字段 → DRF 返回 JSON**。DRF 已提供列表、分页和响应等通用行为，所以项目不需要为每个接口从头实现一遍。

看完后，试着解释三件事：搜索词在哪里读取、草稿为什么不公开、卡片标题来自哪个字段。然后读[接口说明](api.md)核对理解。

## 前端如何接上

| 顺序 | 文件 | 作用 |
| --- | --- | --- |
| 1 | [浏览器路由](../frontend/src/router/index.js) | `/competitions?view=editions` 打开具体届次列表；旧 `/information/competitions` 路径重定向到新地址 |
| 2 | [赛事页面](../frontend/src/views/CompetitionListView.vue) | 管理目录/届次视图、搜索、分页和加载状态；`view=editions` 时发起本例请求 |
| 3 | [赛事请求](../frontend/src/api/competitions.js) | `listCompetitions()` 调用后端赛事 API |
| 4 | [公共请求配置](../frontend/src/api/http.js) | 统一请求地址、会话和写操作所需的 CSRF 处理 |
| 5 | [赛事卡片](../frontend/src/components/CompetitionCard.vue) | 将后端返回的字段填入已经写好的卡片样式 |

默认 `/competitions` 展示学校赛事目录，调用 [`api/catalog.js`](../frontend/src/api/catalog.js) 的 `listCatalogEntries()`，进入 [`competition_catalog/api_urls.py`](../backend/competition_catalog/api_urls.py)，使用 `CatalogCard.vue`。目录和具体届次是两个读取入口，阅读时先选定一条。

科研列表走另一条已实现的公共 API：

[`ProjectListView.vue`](../frontend/src/views/ProjectListView.vue) → [`api/editorial.js`](../frontend/src/api/editorial.js) → [`public_urls.py`](../backend/information_library/public_urls.py) → [`public_views.py`](../backend/information_library/public_views.py) → [`public_selectors.py`](../backend/information_library/public_selectors.py)。

接口为 `/api/v1/editorial/research/` 及其编号详情，读取已发布数据库记录，保留人工 JSON 补充入口；前端不再直接导入 JSON。`PUBLIC_RESEARCH_ENABLED` 默认关闭，关闭时列表返回 `available=false`，详情不可读取。科研正文、来源和卡片字段见 `research/`，资料导入见[科研交付](releases/research-ai-20261007.md)。

## 按下一件工作找代码

| 你要做什么 | 入口与阅读目标 |
| --- | --- |
| 学习申请和入队 | [组队路由](../backend/teams/urls.py) → [视图](../backend/teams/views.py) → [业务服务](../backend/teams/services.py)；每次只追踪一个动作，不一次通读全部状态 |
| 维护人工赛事资料 | [统一导入命令](../backend/curation/management/commands/load_competition_knowledge.py) → `curation/` 的正文、审核与发布服务；先读[资料交接](competition-search-handoff.md)，区别目录、赛事卡片、资源与知识正文 |
| 读取学习资源 | [资源路由](../backend/resources/urls.py) → [视图](../backend/resources/views.py) → [可见范围](../backend/resources/selectors.py)；公开读取与管理员草稿预览使用不同权限 |
| 了解首页聊天 | [AI 路由](../backend/ai_services/urls.py) → [请求与 SSE](../backend/ai_services/views.py) → [聊天流程](../backend/ai_services/chat.py)；再看 `conversation.py`、`unified.py`、`evidence.py` 和 `client.py` |
| 了解赛事向导 | [向导视图](../backend/ai_services/guide_views.py) → [条件与匹配](../backend/ai_services/guide.py) → [回答校验](../backend/ai_services/guide_answer.py)；此处使用独立的 7 天 Session 状态 |
| 调整检索资料 | [赛事检索](../backend/information_library/competition_search.py) 与 [统一检索](../backend/ai_services/unified.py)；分别追踪赛事正文和资源/科研公开资料，再看索引重建命令 |
| 了解后台汇总与旧关键词入口 | [资料汇总](../backend/information_library/selectors.py) → [内部检索](../backend/information_library/retrieval.py)；该 Python 函数仍保留，不等于完整聊天流程 |
| 了解内部 AI 草稿 | [服务入口](../backend/ai_services/__init__.py) → [服务实现](../backend/ai_services/services.py)；用于通知提取和快讯草稿，配置独立于首页聊天 |
| 维护历史采集与官网监测 | [采集命令](../backend/ingestion/management/commands/sync_competitions.py) → [采集服务](../backend/ingestion/services.py)，或 [目录监测](../backend/competition_catalog/monitor.py)；代码保留，执行与调度需另行配置，普通页面不触发采集 |
| 调整页面样式 | 先找到 `frontend/src/views/` 中对应页面，再看它引用的组件及 `styles/index.css` |

## 第二遍再读的内容

- `tests.py`、`test_*.py`、前端 `tests/`：验证行为的代码。改功能时要看对应测试，初读流程时可先折叠。
- `migrations/`：数据库结构变更记录。团队同步数据库需要它，不能靠删掉文件来简化项目。
- `deploy/`、`compose.yaml`：部署及任务运行配置。先学本机请求流程，再了解运行环境。
- [AI 接入说明](ai-v3.md)、[信息库说明](information-library.md)：区分公共读取、后台权限、模型配置与历史功能。研究资料的申请在官方页面完成，尚未实现站内科研申请业务；收藏仍是模型基础。

阅读时可以先忽略上述细节，修改时仍须保留权限检查、字段校验、事务和必要测试。它们分别防止越权、错误数据及重复或冲突操作。
