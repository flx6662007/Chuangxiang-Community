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

资料与来源见[三批交付](competition-research/README.md)。代码在 GitHub 不代表每位队友数据库已收到资料；这里不以包内记录数代替实际入库数量。

1. 配置目标数据库，应用已有迁移：在 `backend/` 执行 `python manage.py migrate`。`curation/0001_initial` 和 `0002_documentreview_importedobjectrevision` 已在仓库，不另建同名表或改写旧迁移。
2. 将资料包保存在仓库外的持久目录，保留附件相对结构。先校验 ZIP、文件及附件哈希，再运行下方文件校验命令。
3. 先导入 131—255 包，再导入依赖它的 90—130 包；1—89 包无此依赖，可独立处理。复用对象缺失、版本不匹配或被人工修改时，导入会拒绝并回滚该次事务。
4. 使用有导入权限的实际管理员执行 `--preview`，写入会在事务末尾回滚。管理员的预览查看权限不自动授予导入权限，具体权限见各包说明。
5. 正式导入时另存 `导入执行清单.json`，保留原始底稿与随包清单不变；仅在执行副本填写本次操作的 `review.status=approved`、真实确认人和日期，再预演、`--apply`。

```powershell
# 以 backend 为当前目录；Windows 可用 .\.venv\Scripts\python.exe 替代 python。
python manage.py import_curated_competitions "<资料包>/导入清单.json"
python manage.py import_curated_competitions "<资料包>/导入清单.json" --actor-id <实际管理员ID> --preview
python manage.py import_curated_competitions "<资料包>/导入执行清单.json" --actor-id <实际管理员ID> --preview
python manage.py import_curated_competitions "<资料包>/导入执行清单.json" --actor-id <实际管理员ID> --apply
```

**执行清单的 `review` 只确认本次入库操作，不代表事实已核验。** 导入器先保存草稿。按照当前项目决定，整理完成的赛事和知识正文可直接发布，无需逐条内容审核；使用下面的批量发布命令即可。发布不自动开放组队或 AI 问答。

### 赛事与知识正文直接发布

先执行 `python manage.py migrate`，应用 `competitions/0002_direct_publication` 和 `curation/0003_allow_direct_publication`。执行身份需要 `competitions.change_competition`、`curation.change_knowledgedocument`、`curation.add_documentreview`，这些是后台写入权限，访客阅读不需要登录。

```powershell
python manage.py publish_curated_library --package-id tongji-2026-131-255 --package-id tongji-2026-90-130 --package-id tongji-2026-001-089-20261003 --actor-id <维护身份ID> --apply
```

不加 `--apply` 只显示操作范围。赛事使用 `publication_method=direct`，知识正文使用 `review_status=published`；保留现有 `verified/approved` 作为独立核验标记。直接发布保留原文、来源、真实日期与核验时间，不把缺失日期补成当前年份，也不改变招募开关。未知分类的届次暂归“目录赛事”，避免猜测学科。接口向访客返回来源链接，已有隐私字段过滤保持生效。

后台赛事列表和知识文档列表也提供“直接发布所选……”操作。重复执行不会重复生成发布记录，已经撤下的内容不会被该命令重新公开。

### 学习资料公开

本项目的学习资料供所有访客使用。资料包导入完毕后，以有 `resources.change_resource` 权限的管理员运行下列命令。默认只列范围，加 `--apply` 后经 `resources/services.py` 逐条校验链接、标题、介绍和类别，记录版本并发布；已有类别保留，未分类项统一归为“赛事学习资料”。这只是学习外链发布，不声称重新核验了所有远程网站的实时可用性。

```powershell
python manage.py publish_curated_resources --package-id tongji-2026-131-255 --package-id tongji-2026-90-130 --package-id tongji-2026-001-089-20261003
# 确认目标库后，在同一命令末尾添加：--actor-id <实际管理员ID> --apply
```

已发布资源重复执行不会重复生成版本。发布属于对入库内容的后续维护，原资料包不会强行覆盖发布后的记录；下一次修改须走内容维护与版本校验流程。后台 Resource 列表也提供“发布所选已整理学习资料”操作。

导入使用稳定编号、载荷哈希和版本记录去重，不覆盖已被人工修改的数据。正文版本保存资料包根路径，移动包前须安排路径迁移。执行清单、运行报告、本机路径和真实数据库不提交 GitHub。

当前资料来源采用人工整理；`ingestion/` 和目录监测代码为历史实现，保留模型与迁移，不作为本流程启动条件。维护事实时修改对应包的整理底稿，再重新生成派生文件；不要同时修改多份索引形成冲突。
