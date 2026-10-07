# 全国科研资料与 AI 接入交付说明

日期：2026-10-07。基于 `main` 的 `664d72d`，交付范围包括全国科研资料、结构化卡片、招募筛选、多来源链接和科研 AI 接入。代码及本机联调已完成；队长的内测网站需按本文单独部署。

## 功能变化

| 功能 | 交付行为 |
| --- | --- |
| 科研资料 | 120 条实验室／团队资料，研究介绍与可选招募继续复用同一模型 |
| 卡片 | 直接展示学校、研究内容、方向、地点、成果及可选招募字段；空值不显示，使用白色卡片框 |
| 文案与日期 | 去掉通用说明、无招募说明和逐卡核查／原文日期；全库最后核查日期放在“全部科研线索”右侧 |
| 招募筛选 | “仅查看有招募机会”，与搜索、分页共同保存在 URL；排除历史／明确结束条目 |
| 官方资料 | 字段旁提供介绍／成果／招募链接，原有“官方说明”入口保留 |
| 科研 AI | 首页科研栏目及智能模式的科研问题使用结构化事实、关键词与 BGE 混合检索，生成带来源回答 |
| 条件与追问 | 区分本科在读、本科学历、硕士、博士生和博士后；识别兼职、明确跨校资格和学校；支持点名实验室后的追问 |

科研资料供本科生、硕士生、博士生等读者使用，阅读介绍不受学历限制；申请类问题按资格筛选。申请在官方页面完成，不新增站内科研申请业务。

## 数据与接口

资料源覆盖 24 所高校、128 条记录，120 条可导入，8 条来源不可读取的记录只保留在维护数据中。全国包不含同济资料。120 条中，83 条有具体招募字段、15 条只有招募入口、22 条是介绍；98 条附招募来源，排除 4 条历史批次后筛选为 94 条。以上是本批次整理数量，不是实时空缺数量。

共 129 个记录内去重来源页面：120 个主页面、9 个补充页面。同页章节锚点不重复计数。链接没有整理正文时仅作为阅读入口，不当作已读完整论文。

新增迁移 `research/0002_source_published_on`（来源发布日期）和 `0003_card_details`（结构化字段及链接）。沿用 `ResearchSource`、`ResearchRevision` 保存补充来源与版本。导入按稳定编号合并并保留其他记录；主链接不重复建行，来源变化计入版本；预演不落库、重复应用不变、下架条目不恢复。

科研列表支持 `recruitment=1`，返回 `details`、全库最后核查日期与统计。聊天沿用 `POST /api/v1/ai/chat/` 和 `mode`；科研推荐增加 `facts`、`field_links`，引用按介绍／成果／招募区分。赛事继续使用原有检索链路。

## 提交范围

精确清单为 [`research-ai-20261007.files.txt`](research-ai-20261007.files.txt)，共 41 个文件：后端 22、前端 8、资料／文档 8、维护脚本 2、忽略规则 1。每行一个仓库相对路径，包含：

| 分类 | 路径与作用 |
| --- | --- |
| 数据模型与导入 | `backend/research/`、`backend/common/snapshots.py`、科研导入命令：迁移、字段验证、来源及版本维护 |
| 公共接口 | `backend/information_library/` 相关选择器、列表视图和测试：字段、筛选、统计与发布边界 |
| AI | `backend/ai_services/` 科研检索、统一检索、索引、聊天、证据、引用及测试 |
| 前端 | 科研卡片、字段链接组件、科研列表／信息中心、样式、聊天组件、响应解析及测试 |
| 必要资料 | `records.json`、`research-cards.json`：可维护资料源与实际导入包，支持可重复生成 |
| 维护工具 | 精简后的资料构建器、科研评测脚本、30 道固定题；属于可复用验证工具 |
| 文档 | 本交付说明、精确清单、资料 README、AI 维护说明、精简进度摘要及忽略规则 |

不提交：`.env`／密钥、数据库及备份、模型、NPZ 索引、虚拟环境、依赖目录、构建产物、截图、日志、临时候选包、离线审阅 HTML／Excel、生成来源索引／检查报告和一次性 Excel 导出脚本。审阅文件已移至被忽略的 `.local/research-national/submission-prep-20261007/`，没有删除。

按清单精确暂存并检查的命令：

```powershell
git add --pathspec-from-file=docs/releases/research-ai-20261007.files.txt
git diff --cached --stat
git diff --cached --check
git diff --cached
```

建议提交标题：`feat: 接入全国科研资料、结构化卡片与科研 AI`。

## 接入步骤

在仓库根目录运行。目标机器需已配置项目 Python 环境、Node.js 和 PostgreSQL，首次搭建见[后端开发](../backend-development.md)。先备份目标数据库，再更新代码和迁移；目标环境使用自己的 `.env`、账号与数据库。

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-retrieval.txt
backend/.venv/Scripts/python.exe backend/manage.py migrate --noinput
backend/.venv/Scripts/python.exe scripts/build-national-research-package.py --check

# 先预演，核对新增、更新、保留数量及来源冲突。
backend/.venv/Scripts/python.exe backend/manage.py import_research_materials --source docs/research-national/20261007/research-cards.json --database --publish
# 确认目标环境与预演结果后应用。
backend/.venv/Scripts/python.exe backend/manage.py import_research_materials --source docs/research-national/20261007/research-cards.json --database --publish --apply
```

目标环境的 `backend/.env` 配置：

| 配置项 | 要求 |
| --- | --- |
| `PUBLIC_RESEARCH_ENABLED` | 设为 `1` 才开放科研页面及 AI 资料；仓库默认关闭 |
| `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` | 使用目标环境有效配置，密钥仅放服务器 |
| `COMPETITION_EMBEDDING_MODEL_PATH` | 固定版本 BGE 模型目录的绝对路径，可复用已有模型 |
| `UNIFIED_SEMANTIC_INDEX` | 科研／资源 NPZ 索引的绝对路径，放本机可写且被忽略的目录 |

模型未准备时执行 `backend/.venv/Scripts/python.exe scripts/prepare-competition-model.py`，随后构建索引和前端：

```powershell
backend/.venv/Scripts/python.exe backend/manage.py rebuild_unified_index
Push-Location frontend
npm ci
npm run build
Pop-Location
```

重启后端加载 `.env`，按现有部署方式更新前端。本机开发启动：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1 -NodePath 'C:/Program Files/nodejs/node.exe'
```

访问 `http://127.0.0.1:5173/research`、`http://127.0.0.1:5173/#ai`；Node 路径按机器调整。队长内测环境沿用原有启动、域名和账号配置。

统一索引升级为 schema 2，保存字段、来源和版本。旧索引或资料变化触发关键词降级，重建后恢复语义检索。不要替换独立的 `COMPETITION_SEMANTIC_INDEX`。本机 120 条科研资料生成 231 个片段；部署库若有其他公开资源，片段数会不同。

## 验收与结果

```powershell
backend/.venv/Scripts/python.exe backend/manage.py test ai_services research.test_importer curation.test_research_import information_library --settings=config.test_settings --noinput
Push-Location frontend
npm test
npm run build
Pop-Location
backend/.venv/Scripts/python.exe scripts/evaluate-research-search.py --output .local/research-national/ai-review/evaluation.json
backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
git diff --check
```

- 后端 203/203、前端 61/61 及构建通过，迁移检查无缺失；后端测试使用独立 SQLite。
- 固定 30 题中，22 道定向题前五条命中：旧字段关键词基线 15/22，新关键词与真实 BGE 混合均 22/22；8 道条件检查通过，无重复结果。这不代表任意自然语言问题的准确率。
- 本机重复导入预演：120 条不变，保留 4 条已有样例，样例不公开展示。
- 真实模型及浏览器已验证：研究介绍／成果分别引用来源；本科资格追问不误报为可申请；存储研究组介绍与招募链接对应不同页面。

整理提交范围后另做交付完整性检查：41 个路径均存在且恰好覆盖本轮待提交变更；仅复制资料源与导入包到隔离目录，构建、`--check` 均通过，导入包内容未变化且不再生成审阅文件。新增文档相对链接有效，`git diff --check` 通过。再次运行 `manage.py test ai_services.test_research_retrieval research.test_importer curation.test_research_import information_library.test_public_api --settings=config.test_settings --noinput`，33/33 通过。

目标环境人工复核科研页搜索、筛选、分页及字段／主来源链接；首页选择科研后用完整句子提问，再追问资格，核对引用。`/api/v1/ai/status/` 的 `chat_configured=true` 只证明配置格式有效，仍需一次真实回答验证密钥和网络。

## 维护与回退

资料更新：改 `records.json` → 构建 → 预演 → 应用 → 重建索引。见[资料维护说明](../research-national/20261007/README.md)和[AI 说明](../ai-v2.md)。

复杂否定及多个实验室之间的指代尚未完整覆盖；没有确认实时名额或读取全部论文全文。首页下方科研预览区仍有历史“暂不开放”文案，本轮接入科研列表及 AI 栏目，该预览区不代表后端开关状态。

临时停用可设 `PUBLIC_RESEARCH_ENABLED=0` 并重启，保留数据。完整回退使用升级前代码和数据库备份；模型与索引可重新生成。
