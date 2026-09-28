# 代码导读

先跟着“打开赛事列表”读完一次请求。掌握这一条流程后，再看组队、采集和 AI；不必从第一个文件开始逐个通读。

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

以 `GET /api/v1/competitions/?search=人工智能` 为例：

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
| 1 | [浏览器路由](../frontend/src/router/index.js) | 将 `/information/competitions` 对应到信息中心中的赛事页面 |
| 2 | [赛事页面](../frontend/src/views/CompetitionListView.vue) | 管理搜索、分页、加载状态，发起读取请求 |
| 3 | [赛事请求](../frontend/src/api/competitions.js) | `listCompetitions()` 调用后端赛事 API |
| 4 | [公共请求配置](../frontend/src/api/http.js) | 统一请求地址、会话和写操作所需的 CSRF 处理 |
| 5 | [赛事卡片](../frontend/src/components/CompetitionCard.vue) | 将后端返回的字段填入已经写好的卡片样式 |

项目招募暂时使用[公共人工资料](../backend/information_library/data/editorial.json)，通过前端 `data/editorial.js` 导出；它尚未改成科研数据库的公共 API。

## 按下一件工作找代码

| 你要做什么 | 入口与阅读目标 |
| --- | --- |
| 学习申请和入队 | [组队路由](../backend/teams/urls.py) → [视图](../backend/teams/views.py) → [业务服务](../backend/teams/services.py)；每次只追踪一个动作，不一次通读全部状态 |
| 了解自动采集 | [采集命令](../backend/ingestion/management/commands/sync_competitions.py) → [采集服务](../backend/ingestion/services.py)；需要理解网页提取时，再看 `adapters.py` 和 `ncda.py` |
| 按学校目录监测官网 | [目录配置](../backend/competition_catalog/data/tongji-2026.json) → [初始化](../backend/competition_catalog/registry.py) → [官网监测](../backend/competition_catalog/monitor.py)；只存后台原文，不直接发布卡片 |
| 给 AI 准备资料 | [内部检索](../backend/information_library/retrieval.py) → [资料汇总](../backend/information_library/selectors.py)；看哪些内容能进入检索、返回哪些来源和状态 |
| 了解模型调用 | [AI 服务入口](../backend/ai_services/__init__.py) → [AI 服务](../backend/ai_services/services.py)；当前用于通知提取和快讯草稿，尚不是已上线的聊天助手 |
| 调整页面样式 | 先找到 `frontend/src/views/` 中对应页面，再看它引用的组件及 `styles/index.css` |

## 第二遍再读的内容

- `tests.py`、`test_*.py`、前端 `tests/`：验证行为的代码。改功能时要看对应测试，初读流程时可先折叠。
- `migrations/`：数据库结构变更记录。团队同步数据库需要它，不能靠删掉文件来简化项目。
- `deploy/`、`compose.yaml`：部署及任务运行配置。先学本机请求流程，再了解运行环境。
- `research/`、`newsletters/`、`resources/`、`favorites/`：部分是已有模型基础；不能根据目录存在就判断功能已开放。当前实现看[团队进度](progress.md)。

阅读时可以先忽略上述细节，修改时仍须保留权限检查、字段校验、事务和必要测试。它们分别防止越权、错误数据及重复或冲突操作。
