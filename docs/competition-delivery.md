# 赛事知识系统第一版交付

资料版本：`874ccd5c6dddf794`。新版资料采用统一的独立导入流程，供 AI 检索和问答使用。旧版资料保留现状。

使用链路：**新版资料包 → 一次导入并记录审核 → 数据库检索 → 返回正文、匹配理由和来源 → 队友接入聊天。**

## 交付内容

下载入口：[三个交付包及校验清单](../deliverables/competition-knowledge-v1/README.md)。

| 文件 | 内容与用途 |
| --- | --- |
| `competition-materials` | 阅读版、CSV、20 项样本、JSON 和 JSONL；解压后打开 `index.html` |
| `competition-integration` | 独立导入命令、三种检索模式、150 题评测、工具与接入说明 |
| `competition-maintenance` | 三个独立导入 JSON、来源证据、处理清单、底稿快照与重建输入 |

正式资料包含 198 条文档、864 个段落，覆盖 188 项目录；其余 67 项的处理结论位于维护包。资料成品和维护记录分别组织，模型使用检索返回的正文与证据。

## 从导入到检索

依照[接入说明](competition-search-handoff.md#准备环境)安装依赖并配置数据库。以下 PowerShell 命令在仓库根目录执行：

```powershell
$actorId = [int](Read-Host '管理员用户 ID')
.local/retrieval-venv/Scripts/python.exe backend/manage.py load_competition_knowledge --actor-id $actorId --apply --reason '启用赛事知识版本 874ccd5c6dddf794'
.local/retrieval-venv/Scripts/python.exe scripts/competition-search.py '英特尔杯' --database --mode keyword --as-of 2026-10-04
```

导入命令读取 `docs/competition-knowledge-maintenance/imports/` 的三份新版 JSON，在一个事务内完成导入和文档审核。首次完整导入后有 198 条可检索文档；相同版本再次导入复用现有记录。`--preview` 可预演整条流程并输出统计。

检索支持 `keyword`、`semantic`、`hybrid`。语义与混合模式使用本地 BGE 中文模型；[接入说明](competition-search-handoff.md#语义与混合检索)提供模型准备和数据库索引命令。

## AI 接入

队友从 Django 后端调用 `information_library.competition_search.search_competitions()`，读取 `knowledge_results` 或 `hits`，把 `passages` 和 `evidence` 提供给模型。输入条件、结果字段和示例见[Python 接口](competition-search-handoff.md#python-接口)。

本次交付完成资料导入与检索。现有 `/api/v1/ai/chat/` 的检索调用、模型上下文组装及前端来源展示由聊天接入同学完成。

## 维护与验证

维护顺序：修改来源底稿或补核事实 → 重建正文及导入包 → 执行统一导入命令 → 重建数据库索引。文档代码保持稳定，新内容保存为新版本。

题集与三种模式对比见[评测报告](competition-evaluation/REPORT.md)；最新独立导入验证见[独立导入验收](competition-knowledge-maintenance/independent-import-report.md)。资料参考日为 2026-10-04，已确认报名开放 0 条、关闭 22 条、信息不足 176 条；检索按各题参考日期判断报名窗口。
