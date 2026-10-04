# 赛事知识与检索接入

本模块提供资料成品、Python 检索函数、导入包和可复现评测。问答 API、自然语言条件解析和聊天界面由接入方调用本模块实现。

## 交付目录

| 路径 | 用途 |
| --- | --- |
| `docs/competition-knowledge/index.html` | 可直接打开的赛事阅读版，支持本地关键词查找 |
| `docs/competition-knowledge/赛事指南.md`、`20项样本.md` | 按赛事与届次组织的正文 |
| `docs/competition-knowledge/competitions.csv` | UTF-8 BOM 总表；空单元格表示未收录该字段 |
| `docs/competition-knowledge/corpus.json` | 独立检索使用的版本化数据 |
| `docs/competition-knowledge/chunks.jsonl` | 带赛事、章节、来源和内容哈希的段落 |
| `docs/competition-knowledge/sources.json`、`version.json` | 来源定位和数据版本 |
| `docs/competition-knowledge/learning-resources.json` | 学习资料与所属赛事关系 |
| `docs/competition-knowledge-maintenance/` | 处理结论、原始资料快照、补核事实、导入包和验收记录；仅维护使用 |
| `docs/competition-evaluation/` | 100 道开发题、50 道冻结验收题与三模式报告 |

模型上下文使用检索返回的 `hits` / `knowledge_results` 及其 `passages`、`evidence`。原始底稿、处理清单和导入包中的目录背景不进入模型上下文。

## 安装与独立演示

以下 PowerShell 命令在仓库根目录执行，使用 Python 3.13。语义依赖安装到独立环境；关键词计算使用 Python 标准库，Windows 下自动取得上海日期还需要 `tzdata`（后端依赖已包含）。也可以显式传入 `as_of`。数据库模式另需后端依赖。

```powershell
python -m venv .local/retrieval-venv
.local/retrieval-venv/Scripts/python.exe -m pip install -r backend/requirements-retrieval.txt
.local/retrieval-venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.local/retrieval-venv/Scripts/python.exe scripts/prepare-competition-model.py
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py --build-index
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py '机器人设计与编程' --mode hybrid --as-of 2026-10-04
backend/.venv/Scripts/python.exe scripts/competition-search.py '诵读中国' --mode keyword --filters '{"team_size":3}' --as-of 2026-10-04
```

模型固定为 `BAAI/bge-small-zh-v1.5`，revision 为 `7999e1d3359715c523056ef9478215996d62a620`。准备模型时需要网络；查询时强制本地加载，使用 CPU，不执行远程模型代码。默认模型目录为 `.local/models/bge-small-zh-v1.5`，索引为 `.local/competition-search/index.npz`。二者均为本地缓存，不纳入 Git。

依赖的精确版本见 `backend/requirements-retrieval.txt`。[模型说明](https://huggingface.co/BAAI/bge-small-zh-v1.5)标注 MIT 许可，准备脚本同时保存该 revision 的说明和许可文件。运行环境和真实耗时见评测报告；首次模型载入耗时与后续查询分别理解。

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

离线语料与数据库公开语料拥有不同的版本标识；分别构建索引。非法参数抛出 `ValueError`，接入方应转换为参数错误响应。

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

参赛专业不能从赛事学科类别推断；缺少年级或专业限制证据不能解释为“不限”。人数匹配需上下界及两者证据齐全。通过所传字段仅表示这些条件有依据地满足，其他邀请、院校推荐、赛区等限制仍保留在资格正文中。

本地自然语言解释只提供有限的主题和偏好提取。接入方将用户明确提出的硬条件映射到 `filters`，不要依靠本地解释器完成复杂意图解析。

### 输出字段

| 字段 | 用途 |
| --- | --- |
| `interpretation` | 兼容现有前端的专业、年级、兴趣与参赛形式解析 |
| `hits` | 按排名组织的统一命中列表，包括赛事代码、届次、字段、理由、正文片段、来源和内容版本 |
| `results` | 有真实已发布 Competition 对象的卡片；保留 `competition`、`matchReason` |
| `knowledge_results` | 只有目录知识的证据；接入问答，不生成虚构赛事详情链接 |
| `mode_used`、`warnings` | 实际模式与降级原因；调用方应记录诊断 |
| `empty_result` | 无结果原因与条件诊断 |
| `corpus_version`、`as_of` | 本次使用的数据版本与参考日期 |

`evidence` 中的 `quote` 仅保存经过核对的逐字引文。当前来源主要是原文位置与整理摘要，空 `quote` 不等同于缺失来源。`passages.text` 是公开赛事正文，不应向用户标为官方逐字引文。

完整实测请求和返回值见 [接口样例](competition-knowledge-maintenance/api-examples.json)：本科三人队查找英特尔杯，以及指定参考日查询仍可报名的赛事。后者的空结果保留逐项条件诊断。

现有 Vue 聊天组件只消费卡片 `results`。接入同学需增加 `knowledge_results` 的证据展示及 `empty_result` 的条件提示；本次保留既有页面入口，没有更换问答接口或修改聊天组件。离线语料的 `competition_id` 均为空，独立演示返回知识证据；数据库适配器才从真实关联取得业务对象。

## 检索规则与更新

先按字段筛选，再进行名称、简称、别名和关键词召回，以及 BGE 向量召回。混合模式采用 RRF（常数 60），符合条件的精确名称优先。长查询的普通关键词召回要求至少两个词项命中和最低覆盖率，避免凭一个泛词返回不相关赛事。主题相似度只参与相关性排序，不能替代资格证据。

当前语义阈值为 `0.60`，来自开发集及库外主题探针的比较，可通过 `COMPETITION_SEMANTIC_THRESHOLD` 配置；调整后重新运行开发集和探针。排名分数不是资格满足概率。超过模型实际 token 上限的查询明确降级，不静默截断问题。

报名窗口按日期闭区间判断；仅有结束日期时不推断已经开放。官方已发布的精确时刻保留在正文，当前 `as_of` 接口为日期粒度，不承担截止日内小时级实时判断。历史资料按原届次返回。

向量索引保存模型标识、revision、语料版本、记录哈希、实际内容指纹和段落证据。内容更新、审核撤下、关联赛事撤下或索引损坏时，旧索引不继续参与排序。数据库正文与版本元数据不一致的文档停止返回。不可用语义索引会显式降级为关键词模式，评测将降级记为运行错误，不计为混合成功。

资料维护顺序：修改原始底稿或具有来源定位的 `verified-supplements.json` → 重建知识包 → 重新生成导入包 → 导入并完成原有审核流程 → 重建对应公开语料索引。不要只修改 HTML、CSV 或 NPZ。

## 重建与导入

首次在队友环境导入知识，使用交付的独立知识包。它们包含全部 198 条文档，不依赖原资料包附件，也不创建实际赛事卡片：

```powershell
python scripts/build-knowledge-imports.py --standalone
cd backend
.venv/Scripts/python.exe manage.py import_curated_competitions ../docs/competition-knowledge-maintenance/standalone-imports/import-001-089.json
.venv/Scripts/python.exe manage.py import_curated_competitions ../docs/competition-knowledge-maintenance/standalone-imports/import-090-130.json
.venv/Scripts/python.exe manage.py import_curated_competitions ../docs/competition-knowledge-maintenance/standalone-imports/import-131-255.json
```

以上命令验证格式；资料包审核、`--preview`、`--apply` 和文档审核继续使用现有流程。独立包导入后为草稿，审核后以问答证据返回。独立模式与下方关联已有赛事模式择一使用；相同文档代码属于不同资料包时，导入器会拒绝混用。已采用一种模式的数据库应继续使用该模式。

重建公开资料，或为已具备原始完整父包的数据库重建关联文档：

```powershell
backend/.venv/Scripts/python.exe scripts/build-competition-knowledge.py
backend/.venv/Scripts/python.exe scripts/build-knowledge-imports.py --original docs/competition-knowledge-maintenance/source-snapshots/001-089/导入清单.json --original docs/competition-knowledge-maintenance/source-snapshots/090-130/导入清单.json --original docs/competition-knowledge-maintenance/source-snapshots/131-255/导入清单.json
```

知识构建命令默认读取本仓库交付的三批 `source-snapshots`，无需原作者的 D 盘资料库。通过 `--package-1`、`--package-2`、`--package-3` 可以指定其他输入目录。要在另一个目录复现，使用 `--maintenance` 指定新的维护输出目录，并复制 `verified-supplements.json`、`rechecked-supplements.json`、`recheck-review.json`、`public-text-revisions.json` 四个输入，使用 `--supplements` 指向其中的 `verified-supplements.json`。

以下命令自动使用交付快照和四个维护输入，在 `.local` 内重建并比较全部公开文件的字节及 SHA-256，无需原资料库目录：

```powershell
backend/.venv/Scripts/python.exe scripts/check-knowledge-rebuild.py --output docs/competition-knowledge-maintenance/rebuild-report.json
backend/.venv/Scripts/python.exe scripts/check-competition-knowledge.py --output docs/competition-knowledge-maintenance/quality-report.json
```

关联导入包位于维护目录 `imports/`。它们通过来源包和 payload hash 引用已有届次；使用这一模式必须先取得并导入原有完整依赖包，再处理覆盖文档。交付的 `source-snapshots` 是重建输入，未包含原始附件二进制，不能代替完整父包。新环境使用上方 `standalone-imports/` 即可导入全部知识。

```powershell
cd backend
.venv/Scripts/python.exe manage.py import_curated_competitions ../docs/competition-knowledge-maintenance/imports/import-001-089.json
```

此命令仅验证。原有 `--preview` 在事务内预演并回滚；`--apply` 将经过资料包审核的内容导入为文档草稿。资料包审核与文档版本审核仍按现有 curation 流程处理，关联赛事也需已发布。交付文件中的离线可检索标记不会越过数据库审核边界。

## 回归与验收

```powershell
.local/retrieval-venv/Scripts/python.exe scripts/build-competition-evaluation.py --check
.local/retrieval-venv/Scripts/python.exe scripts/test-competition-evaluation.py
$env:COMPETITION_EMBEDDING_MODEL_PATH=(Resolve-Path .local/models/bge-small-zh-v1.5).Path
.local/retrieval-venv/Scripts/python.exe scripts/evaluate-competition-search.py --split dev --index .local/competition-search/index.npz --output docs/competition-evaluation/dev-report.json
.local/retrieval-venv/Scripts/python.exe scripts/evaluate-competition-search.py --split test --index .local/competition-search/index.npz --output docs/competition-evaluation/test-report.json
```

题集分组、证据标注、冻结流程、错误和各指标的计算规则见 `competition-evaluation/README.md`。开发集用于调参，验收集用于方案确定后的报告。报告绑定语料版本、题集哈希和运行环境。

数据库测试使用 `config.postgres_test_settings` 与预建的 `test_chuangxiang_dev`，加 `--keepdb --noinput`。真实资料包测试通过 `KNOWLEDGE_DELIVERY_PACKAGE_90`、`KNOWLEDGE_DELIVERY_PACKAGE_131` 显式指定两批原始导入文件；所有写入均在测试库事务内。
