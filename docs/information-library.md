# 信息库与公共资料读取

更新至 2026-10-08。`information_library/` 同时保留管理员只读汇总、内部关键词函数，提供科研/快讯公共读取及赛事混合检索。模型问答由 `ai_services/` 组织，见[AI 接入](ai-v3.md)。以下描述代码权限和数据路径，不表示目标环境已有对应数据或服务。

## 后台入口与权限

本机默认入口为 `http://127.0.0.1:8000/admin/information-library/`。用户须登录、启用且为 staff，并至少具有对应类型的一项权限：

| 内容类型 | 查看或修改权限 |
| --- | --- |
| 赛事 | `competitions.view_competition` 或 `competitions.change_competition` |
| 科研/项目招募 | `research.view_researchopportunity` 或 `research.change_researchopportunity` |
| 快讯 | `newsletters.view_newsletter` 或 `newsletters.change_newsletter` |

只显示获权类型，直接请求其他类型也会拒绝；支持关键词、类型、发布状态筛选及每页 20 条分页。后台可按权限查看草稿、已发布及已撤下记录，详情显示来源、日期、状态和维护位置。这个汇总页面只读，拥有修改权限不会在此增加编辑操作，也不会自动创建管理员或授权。

## 资料来源与维护

| 类型 | 来源 | 当前维护方式 |
| --- | --- | --- |
| 赛事 | `Competition` 及来源；人工知识正文另由 `curation` 管理 | 人工整理、编审导入与受控发布为主；历史采集/官网监测代码仍保留，信息库不另存一套赛事 |
| 科研 | `ResearchOpportunity`、`ResearchSource`、结构化卡片及人工 JSON 补充 | 已支持数据库导入、来源与版本维护；全国资料包见下文，申请仍在官方页面完成 |
| 快讯 | `Newsletter` 当前版本、引用及人工 JSON 补充 | 公共读取已实现，完整在线编辑/确认流程仍待接入；模型存在不等于已有真实快讯 |

全国科研包位于 `docs/research-national/20261007/`，可导入 120 条资料；这是版本化资料包的数量，不是本机数据库计数或实时招募名额。按[科研交付](releases/research-ai-20261007.md)运行 `import_research_materials --database --publish` 先预演，再按目标环境执行 `--apply`。后续维护原资料、构建导入包、应用变更并重建科研索引。

`backend/information_library/data/editorial.json` 保留 `laboratories`、`newsletters` 人工补充入口；当前仓库两项均为空。前端通过 HTTP API 读取，不再直接导入这个文件。数据库已有同源科研记录时，包括草稿和撤下状态，旧人工副本不会重新公开。该文件属于可公开的资料源，不存放私有草稿、账号、审核记录或密钥；旧人工维护流程见[内容维护](undergraduate-labs.md)。

原文日期、核查日期与截止时间分别保留。历史资料、介绍性线索和名额待确认的内容，不能解释为正在接收申请。`demo-` 与明确虚构样例不进入公共汇总。

## 公共读取接口

| 路径 | 读取范围 |
| --- | --- |
| `/api/v1/editorial/research/` | 科研列表；支持 `search`、`recruitment=1` 和分页，返回结构化字段、来源链接及统计 |
| `/api/v1/editorial/research/<pk>/` | 已公开数据库科研记录详情，人工 JSON 补充项没有数据库编号详情 |
| `/api/v1/editorial/newsletters/` | 当前已确认的公开快讯及人工补充；检查引用对象与版本 |
| `/api/v1/resources/` | 独立的 `resources` 模块提供资源列表、详情和筛选选项；不是后台信息库路由 |

科研公开读取及 AI 资料受 `PUBLIC_RESEARCH_ENABLED` 控制，默认关闭：列表返回空结果及 `available=false`，详情返回 404。后台有权限的管理员仍可读取科研记录。启用开关不会自动导入或发布资料。

公共接口使用字段白名单并清理可识别的联系方式；管理员后台权限不能用于扩大公共响应。公开卡片与可作 AI 证据的范围还需分别判断：AI 检索额外要求有效来源、核验和状态依据。

## 保留的内部关键词函数

[`retrieval.py`](../backend/information_library/retrieval.py) 提供 Django 初始化后可调用的 Python 函数，不是 HTTP 路由：

```python
from information_library.retrieval import search_knowledge

items = search_knowledge('机器人', kinds=['research'], limit=5)
for item in items:
    print(item['title'], item['status_note'], item['source_urls'])
```

`query` 最多 200 字符，按空白拆词，所有词须在标题或正文出现；空词可列出合格内容。`limit` 为 1～50 整数；`kinds` 可选 `competition`、`research`、`newsletter`，省略查全部。非法参数抛出 `ValueError`。函数只读当前数据，不调用模型、网络或向量检索，也不执行采集或写入；科研仍受公开开关约束。

| 返回字段 | 用途 |
| --- | --- |
| `id`、`kind`、`title`、`text` | 标识、类型及公开正文 |
| `source_urls`、`source_dates`、`verified_at` | 来源、原文日期、核查时间 |
| `updated_at`、`published_at`、`version` | 内容时间和版本，未知可为空 |
| `publication_status`、`content_status`、`status_note`、`dates` | 发布状态、历史或待确认边界及已知截止日期 |

仅收录有依据的已发布内容；草稿、撤下、虚构样例或缺乏有效核查依据的条目不返回。快讯引用须对应当前公开对象及版本，不能仅凭旧快照的 `published` 标签进入检索。

## 当前 AI 使用路径

首页聊天并非只调用上述函数：赛事通过 `competition_search.py` 与 `ai_services/competition_knowledge.py` 使用公开正文、关键词及 BGE；资源/科研由 `ai_services/unified.py` 汇总后检索，再组装证据生成回答。两份索引和可选联网配置见[AI 接入](ai-v3.md)。

后台可见草稿不能直接交给公共助手。回答须保留来源、时间及待确认状态；模型不代替用户发布、申请、入队或改变权限。来源正文始终是资料，不能当作系统指令。功能代码、历史验收和目标环境是否已导入并启用，需分别记录。
