# 目录 1—89：赛事资料与入库

整理日期：2026-10-03。依据《同济大学本科生学科竞赛目录（2026版）》，原表第 68 项涉及两个部门，此处合并为同一赛事。

## 阅读入口

GitHub 可直接阅读以下清单；HTML 和 Excel 下载到本地后打开。

文件清单中的文本大小和 SHA-256 按 CRLF 转 LF 后计算，XLSX 按原始字节计算，避免 Windows 与 macOS 换行差异导致误报。

| 内容 | 文件 |
| --- | --- |
| 第 1—22 项 | [赛事信息与学习资料](001-022.md) |
| 第 23—44 项 | [赛事信息与学习资料](023-044.md) |
| 第 45—66 项 | [赛事信息与学习资料](045-066.md) |
| 第 67—89 项 | [赛事信息与学习资料](067-089.md) |
| 可搜索阅读版 | [开始阅读.html](开始阅读.html) |
| 筛选表格 | [总索引.xlsx](总索引.xlsx) |
| 事实维护源 | [整理底稿.json](整理底稿.json) |
| 入库输入 | [导入清单.json](导入清单.json) |
| 来源、附件与统计 | [来源清单](来源清单.json) · [附件清单](附件清单.json) · [批次报告](批次报告.json) |
| 传输文件校验 | [文件大小与 SHA-256](文件清单.json) |

## 内容与边界

本批记录 **89 项赛事、121 条赛事来源、212 条学习资料，共 267 个不同链接**。资料类型包括规则、模板、赛题、课程、案例、代码与工具。

- `page_read`：已读来源页面，不代表页面内所有附件、课程或视频已读。
- `official_index`：已确认官方索引或附件入口，资料正文待核对。
- `search_result`：仅取得搜索结果，直接页面正文待核对。

来源对应关系为 73 项已确认、5 项对应范围待确认、11 项来源对应尚未充分核验。这里的“已确认”只指来源与目录的对应关系，官方索引也可能支持该判断，不是参赛规则逐字段验收通过。另按更严格的阅读口径，有15项尚无已读赛事来源页面；它与“11项来源对应未确认”不是同一统计。

| 重点待确认 | 问题 |
| --- | --- |
| 52 · WUPENICITY 调研报告竞赛 | “智慧低碳交通”是否是目录限定主题 |
| 57 · 第十届物流设计大赛 | 目前取得的是第九届资料，不能代替第十届 |
| 63 · 日本大学生方程式 | 目录是否特指 ICV 组 |
| 64 · iF 设计奖 | 专业奖与学生奖的校内认定范围 |
| 67 · 全国工业设计大赛 | 与所找到的“全国大学生工业设计大赛”是否对应 |

**本批交付摘要和链接，没有附带网页、PDF 或视频原件。** 历史资料注明适用届次；目录年份不等于资料年份，也不表示赛事仍可报名。登录、付费和访问受限资料保留实际条件。

## 与 131—255 的格式适配

共用 `backend/curation/` 的模型、版本记录、权限、事务预演和草稿入库流程，仍使用 `schema_version: 1`。本包增加 `catalog_scope: {"first": 1, "last": 89, "batch_size": 25}`；没有此字段的旧包继续按 131—255 校验，原五批分组不变。

| 入库对象 | 数量 | 保存内容 |
| --- | --- | --- |
| `CatalogEntry` | 89 | 目录身份；已有相同记录复用 |
| `Resource` | 207 | 按链接、类型和标题去重的学习资源草稿 |
| `KnowledgeDocument` | 301 | 89 份赛事摘要与 212 份按赛事编写的学习导读 |
| `Competition` | 0 | 尚未整理为单一实际届次的报名字段，本批不创建赛事卡片 |

知识文档的版本、来源、目录/资源关联及核验元数据同时保存。301 份档案不是 301 份原文全文；207 项资源与 212 条学习导读不是统计矛盾，同一资源可用于多个赛事。

**原先本机 `CatalogKnowledgeEntry` 批次存档与本次 `curation` 包是两种存储路径。** 本次只交付统一格式和导入能力，不把旧存档自动迁移为新模型，也不复制数据库到队友电脑。后续使用本包时，以 `curation` 的草稿与版本为准，避免分别维护两份事实。

## 校验与草稿入库

先拉取包含本次适配的 `main`。在已配置 Python、PostgreSQL 和 `.env` 的后端环境中运行，命令均以仓库 `backend` 为当前目录。Windows 虚拟环境可将 `python` 替换为 `.\.venv\Scripts\python.exe`。

1. 应用仓库已有迁移，本次范围适配没有新增数据库迁移：

   ```powershell
   python manage.py migrate
   ```

2. 只校验资料文件，不写数据库、不访问赛事网站：

   ```powershell
   python manage.py import_curated_competitions "../docs/competition-research/tongji-2026-001-089/导入清单.json"
   ```

   预期：`catalog=89, competitions=0, resources=207, documents=301`。

3. 使用目标数据库内已有、具备导入权限的管理员，执行事务预演后回滚：

   ```powershell
   python manage.py import_curated_competitions "../docs/competition-research/tongji-2026-001-089/导入清单.json" --actor-id <管理员ID> --preview
   ```

   管理员权限沿用 [131—255 交付说明](../../curated-competition-package.txt)，不沿用其他电脑的账号 ID，不自动创建管理员或扩大权限。

4. 确认目标库和导入范围后，将 `导入清单.json` **复制到仓库外自己的持久目录**作为 `导入执行清单.json`，仅将副本中的 `review` 改成实际操作记录：

   ```json
   {"status":"approved","reviewed_by":"实际确认人","reviewed_on":"实际日期YYYY-MM-DD"}
   ```

   该记录仅确认草稿导入，不表示所有事实均已核验或允许公开。仓库中的清单始终保留 `pending`；不要把带个人操作记录的执行副本提交到 GitHub。

5. 用执行副本再次预演，再导入：

   ```powershell
   python manage.py import_curated_competitions "<持久目录>/导入执行清单.json" --actor-id <管理员ID> --preview
   python manage.py import_curated_competitions "<持久目录>/导入执行清单.json" --actor-id <管理员ID> --apply
   ```

本包没有附件路径，执行副本可独立保存；若以后增加附件，必须同时保留附件相对目录。执行报告可通过 `--report "<报告目录>/入库结果.json"` 保存。重复导入相同数据应为 unchanged；遇到人工修改冲突时停止并核对，不强行覆盖。

不传 `--batch` 时处理全部 89 项；本包 `--batch 1/2/3/4` 分别对应 1—25、26—50、51—75、76—89。可以重复指定参数选择多批。旧 131—255 包仍使用原五批，每批 25 项。

赛事资料和学习资源均保持草稿，不自动公开、不开放组队、不启用 AI 问答。GitHub 上的交接资料为可公开来源摘要；网站的草稿权限是另一层边界。

## 维护

事实只修改 `整理底稿.json`。目录身份以项目 `backend/competition_catalog/data/tongji-2026.json` 为准。

在仓库根目录执行以下本地转换，使用 Python 标准库，不联网、不入库：

```powershell
python docs/competition-research/tongji-2026-001-089/build_package.py
python docs/competition-research/tongji-2026-001-089/build_index.py
```

这会更新导入清单、来源清单、批次报告、JSONL 与 Markdown/HTML 阅读版。Excel 用 `build_workbook.py` 更新，可选生成依赖为 `openpyxl`，接收方入库无需安装。全部派生内容更新后运行 `build_manifest.py` 更新文件校验清单。派生文件应和底稿一起提交，保留核验等级及缺项。

改进优先级：先补对应范围疑点与直接来源正文，再整理实际届次的资格、报名和截止字段；随后根据授权保存原文或笔记，按现有审核边界接入 AI 检索。
