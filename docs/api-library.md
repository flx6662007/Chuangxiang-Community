# 资料库接口与入库

本页对应人工赛事资料的前后端连接。接口只读取数据库，不访问赛事官网、不调用模型；资料导入和公开发布分别处理。原有账号、赛事日期与组队规则见 [api.md](api.md)。

## 页面与数据

| 页面 | 读取内容 | 后端模型 |
| --- | --- | --- |
| `/competitions` | 学校赛事目录、等级和可见资料数量 | `CatalogEntry` |
| `/competitions?view=editions` | 已发布的具体届次通知 | `Competition`、`CompetitionSource` |
| `/competitions/catalog/:code` | 某一目录的关联届次、知识摘要与正文、资源入口 | `CatalogBinding`、`KnowledgeDocument`、`DocumentRevision`、`DocumentLink` |
| `/resources`、`/resources/:code` | 学习资源、来源和关联目录 | `Resource` |

目录编号不等于届次编号。目录存在但公开资料为零时，页面显示空态，不填充模拟赛事，也不把旧规则改成新一届。资源中心和资源详情允许游客查阅，无需管理员权限。资源与目录的关系使用未撤下文档的**当前版本**关联；读取关联不等于公开该文档正文。

## 访问边界

全部新接口只提供读取。资源中心页面始终读取公开资源，不提供管理员预览开关。目录和知识页面默认读取公开内容；内部程序及有权限的管理员显式传 `preview=1` 时才能预览草稿。

| 内容 | 默认公开范围 | 管理员预览增加的内容 |
| --- | --- | --- |
| 目录 | `is_active=True` 的目录身份 | 身份范围相同，统计数量按预览范围计算 |
| 关联届次 | 已发布、非虚构届次 | 草稿届次；不提供草稿报名或组队入口 |
| 学习资源 | 已发布且 `availability=available`、非虚构资源 | 可用草稿；仍不含下架或不可用资源 |
| 知识文档 | 已直接发布或已核验的当前版本，且关联赛事、资源均非草稿或下架，资源未标不可用 | 额外显示草稿；仍不含已撤下文档 |

预览账户必须已登录、有效、为工作人员，并同时拥有以下四项权限：

```text
competition_catalog.view_catalogentry
competitions.view_competition
resources.view_resource
curation.view_knowledgedocument
```

`GET /api/v1/accounts/me/` 的 `can_preview_library` 仅用于前端显示预览入口。实际权限由每个 API 重新检查；游客、普通学生及权限不全的管理员请求预览均返回 `403`。`preview` 接受 `0/1/false/true`，默认 `0`，其他值返回 `400`。

资源浏览权限与维护权限分开：查看已发布学习链接不要求登录，导入、编辑和发布仍走后台权限。资源公开不会自动审核关联知识正文，也不会发布草稿赛事。

响应采用字段白名单，正文为纯文本，来源为安全 HTTP(S) 外链；不返回本机附件路径、资料根目录、导入操作者及完整内部元数据。当前接口不托管原始附件，也不提供聊天问答。

## 请求与分页

普通业务地址以 `/api/v1/` 开头，路径末尾保留 `/`。前端使用既有会话 Cookie；开发时通过 Vite `/api` 代理连接后端。

三个列表接口共用分页：`page` 默认 1，`page_size` 默认 20、最大 50。页大小非法返回 `400`；无效或越界页返回 `404`；第一页无匹配返回 `200` 和空列表。

```json
{"count":0,"next":null,"previous":null,"results":[]}
```

`next`、`previous` 为完整 URL 或 `null`。筛选后重置页码，不能只在前端过滤当前页。

| 接口 | 列表筛选参数（另支持分页、preview） | 主要返回内容 |
| --- | --- | --- |
| `GET /competition-catalog/` | `search`：名称或编号，≤200 字符；`grade`：等级精确匹配，≤8 字符 | `code/name/version/grade/levels/departments/source_url`，以及 `competition_count/resource_count/document_count` |
| `GET /competition-catalog/<code>/` | 仅 `preview` | 上述目录字段及 `competitions` 数组；届次项为 `id/code/title/edition/summary/publication_status/url` |
| `GET /knowledge-documents/` | `search`：当前标题或正文，≤200 字符；`catalog_code`：目录编号，≤16 字符 | `code/title/edition/review_status/summary/sources/updated_at/version` |
| `GET /knowledge-documents/<code>/` | 仅 `preview` | 列表字段加 `body/body_truncated/notes` |
| `GET /resources/` | `search`：标题、介绍或来源方，≤200 字符；`category/direction`：词条编码，≤64 字符；`catalog_code`：目录编号，≤16 字符 | `id/title/description/facts/category/directions/tags/provider/source_url/updated_at/publication_status/availability/catalogs`；列表 `content` 为空 |
| `GET /resources/<code>/` | 仅 `preview` | 资源字段相同，`description` 为用途摘要，`content` 提供详细介绍，`facts` 提供学习属性 |
| `GET /resources/options/` | 仅 `preview` | `categories/directions/has_unclassified`，来自当前可见资源，不硬编码假分类 |

表中路径均接在 `/api/v1` 后。详情中的 `<code>` 是稳定字符串编号；原有 `/competitions/<id>/` 仍使用整数主键。

资源 `category=unclassified` 可筛选尚未分类的记录。未知资源类别、方向或目录编号返回 `400`；目录与知识搜索无匹配时返回空列表。不存在、不可见或已撤下的详情统一返回 `404`。

知识摘要最多 280 字符；正文最多返回 16,000 字符，`body_truncated=true` 提示原始返回文本达到截断阈值。`sources` 为 `{url,title}` 数组；`notes` 包含 `edition_note/source_status/gaps/contains_source_fulltext`，用于保留资料范围与维护信息。学生页面集中展示正文、届次和来源。

`information_library/presentation.py` 在读取时精简人工整理模板，去掉审核过程提示、重复介绍，将已知字段映射转换成中文信息项。原始资料、版本和数据库字段不变。资源 `facts` 可包含 `kind/difficulty/access/audience/scope/prerequisites/language/learning_path`；只有原文已有的属性才返回。卡片使用用途摘要，详情展示适用范围、基础要求与学习方法。实际比赛限制、年份、费用与适用学校等事实保留。

## 代码位置

| 工作 | 权威入口 |
| --- | --- |
| 总路由 | `backend/config/urls.py` |
| 预览资格与参数 | `backend/curation/api_permissions.py` |
| 目录查询与数量 | `backend/competition_catalog/api_selectors.py` |
| 公开知识与未来 AI 边界 | `backend/curation/retrieval.py` 的 `student_visible_documents()` |
| 知识当前版本与字段 | `backend/curation/selectors.py`、`serializers.py` |
| 资源状态、关联及字段 | `backend/resources/selectors.py`、`serializers.py` |
| 前端目录和知识请求 | `frontend/src/api/catalog.js` |
| 前端资源请求 | `frontend/src/services/resources.js`、`resourceClient.js` |

修改公开范围应改后端查询规则并补权限测试，不用前端隐藏按钮代替。内部信息库和学生 API 的用途不同，不能把内部查询结果直接当公开结果返回。

## 资料入库

赛事知识统一使用新版独立资料包。在仓库根目录执行：

```powershell
python backend/manage.py migrate
python backend/manage.py load_competition_knowledge --actor-id <管理员ID> --apply --reason '启用新版赛事知识'
```

命令在一个事务中导入并公开 198 篇资料，重复运行保持稳定，已撤下资料保持撤下。无需下载旧包附件或按旧批次建立依赖。索引构建、环境变量和助手调用见[赛事助手接入](ai-assistant-handoff.md)。

旧资料保留在维护历史。同一目录已有新版公开正文时，公开知识列表隐藏旧包正文；原赛事、资源和组队记录保留。公开目录不返回内部学校目录来源和责任学院，赛事正文继续保留真实官方来源及资格限制。

资料更新沿用[新版维护与重建流程](competition-search-handoff.md)。
