# 赛事知识系统第一版交付

资料版本：`874ccd5c6dddf794`。交付分支：`codex/competition-knowledge-delivery-20261004`。

下载入口：[三个交付包及校验清单](../deliverables/competition-knowledge-v1/README.md)。直接接续代码时，克隆本仓库并切换到上述分支即可。

| 接收人 | 交付内容 | 使用方式 |
| --- | --- | --- |
| 资料验收、展示同学 | `competition-materials` | 解压后打开 `index.html`，CSV 为总表，JSON/JSONL 为知识数据 |
| AI 接入同学 | `competition-integration` | 检索源码、三种模式、150 题评测和接口说明；保持仓库相对路径，在本项目中接入 |
| 资料维护同学 | `competition-maintenance` | 处理清单、来源、底稿快照、补核输入和两种导入包；保持仓库相对路径 |

成品包包含 11 个文件，共 198 条资料，覆盖 188 项目录；另 67 项的处理记录位于维护包。维护包保存原始目录背景和历史核验过程；比赛展示及模型上下文使用成品包和检索结果中的正文、必要证据。

## AI 接入

优先阅读 [接口说明](competition-search-handoff.md)。默认使用混合模式，接收 `knowledge_results`、`passages`、`evidence` 及 `empty_result`。现有问答 API 与聊天界面由接入方调用本模块。

不准备模型也能先验证关键词流程；从仓库根目录运行：

```powershell
python scripts/competition-search.py '英特尔杯' --mode keyword --as-of 2026-10-04
```

语义模式按接口说明安装固定版本依赖，准备本地 BGE 模型并构建索引。模型缓存、虚拟环境、数据库和原始附件不在交付包中。

## 导入与重建

新数据库使用 `docs/competition-knowledge-maintenance/standalone-imports/` 的三个独立知识包；无需原附件和实际赛事对象，导入仍受资料包与文档审核控制。运行 `python scripts/build-knowledge-imports.py --standalone` 可重建。

`imports/` 是关联已有业务赛事的覆盖包，只适用于已导入完整原始父包的数据库。两种模式不能混用。`source-snapshots/` 用于重建正文和追溯输入，其中历史本机路径仅为原始记录；运行命令不依赖这些路径。

```powershell
python scripts/build-competition-knowledge.py
python scripts/check-knowledge-rebuild.py
python scripts/build-competition-evaluation.py --check
python scripts/package-competition-delivery.py --verify
```

公开资料默认从仓库内快照重建。四份维护输入与三批快照均已交付；来源访问报告记录的抓取缓存、PDF/DOCX 原件未随包提供。

## 验证与接续

原实现验收：200 项后端测试、17 项评测工具测试通过；11 个公开文件重建后逐字节一致。打包阶段新增 3 项独立知识包测试通过，验证 198 条文档无需父包的导入、重复导入、审核及撤下，两种导入模式互斥；公开语料和检索实现未改变。

在仅包含本次成果的交付分支上，产品、检索和实包测试合计 64 项全部通过（73.568 秒），评测工具 17 项通过。三个 ZIP 的 CRC、逐文件 SHA-256、公开资料重建及解压后关键词检索验证通过；原始快照和 CSV 设置了专用 Git 属性，保持交付字节与来源哈希。

固定题集的冻结 Hit@5：关键词 100%、纯语义 80%、混合 100%；混合硬条件违规为 0。混合语义改写增益为开发集 +2.5 个百分点、冻结集 0。完整过程见 [评测报告](competition-evaluation/REPORT.md) 和 [实现验收记录](competition-knowledge-maintenance/acceptance-report.md)。

截至资料参考日，有依据确认报名开放的记录为 0，关闭 22，信息不足 176；专业与年级结构字段分别覆盖 3 条和 1 条。当前包可用于知识问答与检索流程验证，报名推荐继续依官方窗口补核。
