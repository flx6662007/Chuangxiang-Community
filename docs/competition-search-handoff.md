# 新版赛事知识导入与检索

新版资料通过一个命令独立入库，再由 Python 检索接口向 AI 提供正文、匹配理由和来源。数据版本为 `874ccd5c6dddf794`，共 198 条文档、864 个段落。旧版资料保留现状。

## 准备环境

以下 PowerShell 命令均在仓库根目录执行，使用 Python 3.13。数据库连接与 Django 配置写入 `backend/.env`，配置方法见[后端开发说明](backend-development.md)。数据库使用项目现有模型与迁移。

```powershell
python -m venv .local/retrieval-venv
.local/retrieval-venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.local/retrieval-venv/Scripts/python.exe backend/manage.py migrate
```

后续命令使用项目中的有效管理员账号。导入与审核权限为 `curation.add_importrun`、`curation.add_knowledgedocument`、`curation.change_knowledgedocument`、`curation.add_documentreview`，以及既有导入服务使用的赛事、来源和资源维护权限。已有超级管理员可直接执行。

## 统一导入

导入文件固定放在 `docs/competition-knowledge-maintenance/imports/`，三包分别包含 65、41、92 条文档。每包自带目录信息、正文、字段、来源及版本，业务赛事关联为空。

```powershell
$actorId = [int](Read-Host '管理员用户 ID')
.local/retrieval-venv/Scripts/python.exe backend/manage.py load_competition_knowledge --actor-id $actorId --apply --reason '启用赛事知识版本 874ccd5c6dddf794'
```

`load_competition_knowledge` 在一个事务内读取三包、保存文档版本、记录管理员审核并启用检索。审核人来自指定账号，审核日期来自执行日期，`--reason` 保存本次操作依据。JSON 中的初始 `pending` 状态由这次操作完成审核。

首次完整执行后，报告显示 198 条可检索文档。报告同时给出资料版本、数据库语料版本和新增、更新、复用、撤下的数量。再次导入相同内容复用现有版本；更新正文时生成新版本并保留历史记录。已撤下文档维持撤下状态。

需要查看执行结果时，使用相同命令并将 `--apply` 改为 `--preview`；预演执行整条流程后回滚。默认不指定这两个参数时也执行预演。

## 数据库检索

导入完成后直接查询：

```powershell
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py '英特尔杯' --database --mode keyword --as-of 2026-10-04
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py '诵读中国' --database --mode keyword --filters '{"team_size":3}' --as-of 2026-10-04
```

`--database` 使用数据库当前已审核文档。返回的 `knowledge_results` 包含赛事名称、届次、匹配理由、正文片段与来源；`corpus_version` 标识本次检索版本。独立知识数据作为问答证据返回。

资料阅读与离线演示可直接使用 `docs/competition-knowledge/corpus.json`；省略 `--database` 时，查询脚本读取此文件。

## 语义与混合检索

关键词流程完成后，准备中文语义模型和数据库索引：

```powershell
.local/retrieval-venv/Scripts/python.exe -m pip install -r backend/requirements-retrieval.txt
.local/retrieval-venv/Scripts/python.exe scripts/prepare-competition-model.py
$env:COMPETITION_EMBEDDING_MODEL_PATH=(Resolve-Path .local/models/bge-small-zh-v1.5).Path
$env:COMPETITION_SEMANTIC_INDEX=(Join-Path (Get-Location) '.local/competition-search/database-index.npz')
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py --database --build-index --index $env:COMPETITION_SEMANTIC_INDEX
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py '机器人设计与编程' --database --mode hybrid --index $env:COMPETITION_SEMANTIC_INDEX --as-of 2026-10-04
```

向量模型为 `BAAI/bge-small-zh-v1.5`，固定 revision `7999e1d3359715c523056ef9478215996d62a620`，精确依赖见 `backend/requirements-retrieval.txt`。模型首次准备后保存在本地，查询使用 CPU 和本地索引。模型说明及 MIT 许可随模型准备脚本保存。

后端服务进程设置同样的 `COMPETITION_EMBEDDING_MODEL_PATH` 和 `COMPETITION_SEMANTIC_INDEX`。语料更新后重新执行数据库索引构建命令。离线 `corpus.json` 的演示索引与数据库索引分别构建。

## Python 接口

从 Django 后端中直接调用：

```python
from information_library.competition_search import search_competitions

result = search_competitions(
    "诵读中国",
    filters={"participation_type": "team", "team_size": 3},
    preferences={"education": "undergraduate"},
    as_of="2026-10-04",
    mode="hybrid",
    limit=5,
)
```

默认读取数据库当前可见文档。独立使用时传入从 `corpus.json` 加载的 `corpus` 对象和 `index`；后者可以是索引对象或文件路径。服务进程可复用已加载的模型和索引，但每次查询必须使用最新的语料与可见状态。

数据库模式配置示例：

```powershell
$env:COMPETITION_EMBEDDING_MODEL_PATH=(Resolve-Path .local/models/bge-small-zh-v1.5).Path
$env:COMPETITION_SEMANTIC_INDEX=(Join-Path (Get-Location) '.local/competition-search/database-index.npz')
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py --database --build-index --index $env:COMPETITION_SEMANTIC_INDEX
```

离线语料与数据库语料分别构建索引，版本随查询结果返回。非法参数抛出 `ValueError`，接入方转换为参数提示。

### 输入字段

| 字段 | 类型与约定 |
| --- | --- |
| `query` | 最多 500 字符；查询或筛选条件至少提供一项 |
| `filters` | 必须满足的条件；不同键之间为 AND |
| `preferences` | 排序偏好；未命中不排除候选 |
| `as_of` | `YYYY-MM-DD`；默认上海时区当天 |
| `mode` | `keyword`、`semantic`、`hybrid` |
| `limit` | 1—50，默认 5；赛事卡片与纯知识结果共用此数量 |

`filters` 与 `preferences` 接受相同的固定字段：

| 字段 | 值 |
| --- | --- |
| `category` | `categories.json` 中的类别 code |
| `level` | `international`、`national`、`provincial`、`municipal`、`university`、`college`、`other`；未知范围不用于硬筛 |
| `education` | `undergraduate`、`postgraduate`、`master`、`doctorate`、`college`、`high_school`，兼容对应中文名称 |
| `major` | 专业名称；与明确公布的专业名单匹配 |
| `grade` | 年级文本，例如 `大二` |
| `participation_type` | `individual`、`team`、`both` |
| `team_size` | 1—1000 的整数 |
| `registration_status` | `open`、`closed`、`upcoming` |
| `deadline_from`、`deadline_to` | 报名截止日期的闭区间边界；不能用作品截止日期替代 |
| `catalog_codes` | 原目录标识列表，用于指定赛事范围 |
| `code`、`edition` | 精确记录代码、届次文本 |

支持文本列表的条件按同一键内 OR 处理。`both` 表示赛事同时允许个人与团队；过滤 `team` 或 `individual` 都可命中这样的赛事。`education=master` 可以命中明确接受研究生的赛事。

专业与年级按官方明确公布的限制匹配；缺少证据的字段记为信息不足。人数匹配使用有证据的上下界。邀请、院校推荐及赛区限制保留在资格正文中。

接入方将用户明确提出的条件映射到 `filters`，将兴趣、技能等映射到 `preferences`。本地解释器辅助提取主题与偏好。

### 输出字段

| 字段 | 用途 |
| --- | --- |
| `interpretation` | 专业、年级、兴趣与参赛形式的结构化解释 |
| `hits` | 按排名组织的统一命中列表，包括赛事代码、届次、字段、理由、正文片段、来源和内容版本 |
| `results` | 有真实已发布 Competition 对象的卡片；保留 `competition`、`matchReason` |
| `knowledge_results` | 新版独立知识结果，供 AI 问答使用 |
| `mode_used`、`warnings` | 实际模式与降级原因；调用方应记录诊断 |
| `empty_result` | 无结果原因与条件诊断 |
| `corpus_version`、`as_of` | 本次使用的数据版本与参考日期 |

`passages.text` 保存整理后的赛事正文。`evidence` 保存官方链接、原文位置和适用届次；`quote` 有值时为已经核对的官方引文。

完整实测请求和返回值见 [接口样例](competition-knowledge-maintenance/api-examples.json)：本科三人队查找英特尔杯，以及指定参考日查询仍可报名的赛事。后者的空结果保留逐项条件诊断。

当前 Vue 聊天组件调用 `/api/v1/ai/chat/`，请求为 `messages`，响应为 `message.role/content`；详见 [AI 聊天说明](ai-chat.md)。聊天接入同学在这条调用链中调用 `search_competitions()`，读取 `knowledge_results` 或 `hits`。

接入方将返回的正文片段和证据加入模型上下文，并按产品需要展示来源与无结果条件。本次独立知识链路以 `knowledge_results` 提供问答依据，`results` 保留为赛事卡片适配字段。

## 检索规则与更新

先按字段筛选，再进行名称、简称、别名和关键词召回，以及 BGE 向量召回。混合模式采用 RRF（常数 60），符合条件的精确名称优先。长查询的关键词召回要求至少两个词项命中和最低覆盖率。主题相似度参与排序，资格结论来自字段证据。

语义阈值为 `0.60`，可通过 `COMPETITION_SEMANTIC_THRESHOLD` 配置，调整后运行开发集和主题探针。排名分数表达相关性。超过模型 token 上限的查询使用关键词模式，并返回运行诊断。

报名窗口按日期闭区间判断，开始日期缺失时记为信息不足。`as_of` 为日期粒度，官方精确时刻保留在正文。报名截止和作品截止分别判断，历史资料按所属届次返回。

向量索引保存模型标识、revision、语料版本、内容哈希和段落证据。文档撤下后立即退出数据库检索。内容更新、索引过期或模型不可用时，检索使用关键词模式，在 `mode_used` 和 `warnings` 中记录实际状态；更新后重新构建索引即可恢复混合检索。

资料维护顺序：更新底稿或补核事实 → 重建知识包与导入包 → 执行统一导入命令 → 重建数据库索引。

## 数据更新

先更新来源底稿或维护目录中的补核事实，再执行：

```powershell
.local/retrieval-venv/Scripts/python.exe scripts/build-competition-knowledge.py
.local/retrieval-venv/Scripts/python.exe scripts/build-knowledge-imports.py
.local/retrieval-venv/Scripts/python.exe backend/manage.py load_competition_knowledge --actor-id $actorId --apply --reason '更新赛事正文与来源'
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py --database --build-index --index $env:COMPETITION_SEMANTIC_INDEX
```

生成器默认输出三份独立包。每条文档使用稳定的 `final-<record_id>`，内容变化保存新版本；新版移除的文档自动撤下，历史正文保留。命令记录操作者、执行依据和导入结果，检索结果携带新的数据库语料版本。已撤下文档维持撤下状态。

撤下单篇文档时，使用现有审核命令记录当前版本和原因：

```powershell
.local/retrieval-venv/Scripts/python.exe backend/manage.py review_curated_document 文档代码 --revision 当前版本号 --status withdrawn --reason 撤下原因 --actor-id $actorId
```

## 验证与评测

独立导入测试覆盖空库全量加载、关键词查询、重复执行、版本更新、撤下、事务回滚和原数据保留。数据库测试在项目的隔离 PostgreSQL 测试库执行：

```powershell
.local/retrieval-venv/Scripts/python.exe backend/manage.py test curation.test_product curation.test_knowledge_delivery curation.test_knowledge_loader information_library.test_competition_search --settings=config.postgres_test_settings --keepdb --noinput
.local/retrieval-venv/Scripts/python.exe scripts/test-competition-evaluation.py
.local/retrieval-venv/Scripts/python.exe scripts/check-competition-knowledge.py
.local/retrieval-venv/Scripts/python.exe scripts/package-competition-delivery.py --verify
```

检索评测使用固定的 100 道开发题和 50 道冻结题。语料、题集、模型和结果版本记录见[评测说明](competition-evaluation/README.md)与[评测报告](competition-evaluation/REPORT.md)。独立导入的最新执行记录见[独立导入验收](competition-knowledge-maintenance/independent-import-report.md)。
