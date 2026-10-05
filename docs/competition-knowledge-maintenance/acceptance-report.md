# 赛事知识系统第一版验收记录

资料日期：2026-10-04。最终语料版本：`874ccd5c6dddf794`。

本记录保存实现验收时的结果；后续打包与交付分支说明见 [交付入口](../competition-delivery.md)。文末和 JSON 中的未提交状态对应实现验收时点。

本版已交付成品资料、独立检索模块、导入包和评测工具，混合检索达到本次固定题集的验收目标。开发与生产数据库未导入新交付内容；实包导入与审核行为在隔离测试库验证。

## 资料与覆盖

| 项目 | 结果 |
| --- | --- |
| 目录处理 | 255 项全部有结论：188 项正式收录、67 项内部处理 |
| 正式资料 | 198 条记录，含 66 条概览与 132 条具体届次资料 |
| 知识段落与样本 | 864 个段落、20 项跨三批样本 |
| 学习资料 | 308 份，保存所属赛事关系 |
| 来源证据 | 265 个证据对象，对应 238 个不同 URL |
| 匹配字段 | 资格 70、学历 45、参赛形式 63、人数下限 31／上限 44 |
| 日期与入口 | 报名截止 24、作品截止 35、报名入口 38、报名开始 1 |
| 专业与年级 | 明确专业规则 3、明确年级规则 1；缺项不解释为不限 |
| 当日报名状态 | 2026-10-04：有依据确认开放 0、关闭 22、信息不足 176 |

正式收录数表示可用于赛事知识查询的目录覆盖，不表示这些赛事目前均可报名。报名状态统计只依据已收录并有来源的窗口或当天官方状态；它不表示现实中没有开放的赛事。

公开资料使用统一正文和章节模板。已逐项处理 77 条文风候选，完成后又复核了标题、届次、来源位置和学习资料；真实主办方、学校资格限制与官方链接予以保留。原目录背景、底稿、维护说明和核验问题保存在本目录，不进入模型上下文。处理结果见 `processing-report.json`、`editorial-qa-resolution.json`、`title-edition-review.json`。

修正包含跨赛道人数合并、赛事或赛道身份混淆、评审日期与作品截止混淆、历史标题误带目录年份、跨届学习规程，以及原暂缓项目的重新核对。67 项内部条目均有明确原因。地址访问检查完成 272 个 URL，其中 231 个成功取得内容；`source-access-report.json` 记录的是访问结果，不能替代事实核验。

## 检索与评测

提供关键词、纯语义、混合三种模式。混合采用字段筛选、关键词及本地 BGE 召回、RRF 排序，结果带字段判断、理由、正文片段、证据、日期和版本；没有真实赛事对象的记录返回问答证据。

固定模型为 `BAAI/bge-small-zh-v1.5`，revision `7999e1d3359715c523056ef9478215996d62a620`，相似度阈值为 0.60。依赖精确版本见 `backend/requirements-retrieval.txt`。实际语义运行使用本地模型及索引，没有独立向量数据库。

| 集合 | 关键词 Hit@5 | 纯语义 Hit@5 | 混合 Hit@5 |
| --- | ---: | ---: | ---: |
| 100 道开发题中的 90 道有答案题 | 97.78% | 92.22% | 98.89% |
| 50 道冻结题中的 40 道有答案题 | 100% | 80% | 100% |

三种模式在 20 道空结果题和另 2 道独立无主题诊断上全部正确，硬条件违规为 0；理由证据引用与空结果说明覆盖均为 100%。混合在语义改写题上相对关键词提升开发集 2.5 个百分点、冻结集 0 个百分点。纯语义冻结结果低于 90% 门槛，作为对照保留，未据此修改验收参数。

混合的冻结集目标证据命中为 39/40：金犊奖评分问题找回了赛事，但返回片段未包含预先标注的评分依据。理由引用覆盖验证的是来源链；问答 API 接入后仍须评测生成答案是否完整且与具体规则一致。完整失败题、延迟、环境及逐题结果见 [评测报告](../competition-evaluation/REPORT.md)。

首次冻结验收版本为 `e0a771c357d83a62`。UI 复核随后发现第十四届海洋知识竞赛标题误带 2026 目录年，并修正跨届规程链接及第十五届主题。修复后的题集逐字节不变，实现、参数和全部准确性指标不变；两次实测均保留，见 `../competition-evaluation/history/version-review.json`。

## 验证命令与结果

以下命令从仓库根目录执行；Django 命令从 `backend` 执行，解释器使用 `../.local/retrieval-venv/Scripts/python.exe`。

| 命令 | 实测结果 |
| --- | --- |
| `manage.py test curation.tests information_library.tests competitions ai_services --settings=config.postgres_test_settings --keepdb --noinput` | 139 项通过，10.098 秒 |
| `manage.py test curation.test_product curation.test_knowledge_delivery information_library.test_competition_search --settings=config.postgres_test_settings --keepdb --noinput` | 最终版本 61 项通过，97.781 秒，无跳过 |
| `python scripts/test-competition-evaluation.py` | 17 项通过 |
| `python scripts/build-competition-evaluation.py --check` | 150 题、分组、证据、版本及哈希检查通过 |
| `python scripts/check-competition-knowledge.py --output docs/competition-knowledge-maintenance/quality-report.json` | 255 项结论、正文与字段证据、样本、版本及段落一致性检查通过 |
| `python scripts/check-knowledge-rebuild.py --output docs/competition-knowledge-maintenance/rebuild-report.json` | 11 个公开文件从交付快照重建后逐字节一致 |
| `python scripts/competition-search.py --build-index` | 198 条记录／864 段，最终版本索引成功生成 |
| `python scripts/evaluate-competition-search.py --split dev --index .local/competition-search/index.npz --output docs/competition-evaluation/dev-report.json` | 三模式运行完成，混合达标，退出码 0 |
| `python scripts/evaluate-competition-search.py --probes docs/competition-evaluation/negative-probes.json --index .local/competition-search/index.npz --output docs/competition-evaluation/probe-report.json` | 三模式各 2/2 正确空结果，退出码 0 |
| `python scripts/evaluate-competition-search.py --split test --index .local/competition-search/index.npz --output docs/competition-evaluation/test-report.json` | 三模式运行完成，混合达标，退出码 0 |
| `python -m pip check` | 无依赖冲突 |
| `git -c core.whitespace=cr-at-eol diff --check` | 通过 |

语义命令使用 `.local/retrieval-venv/Scripts/python.exe`，并设置 `COMPETITION_EMBEDDING_MODEL_PATH` 为本地模型目录。实包测试设置 `KNOWLEDGE_DELIVERY_PACKAGE_90`、`KNOWLEDGE_DELIVERY_PACKAGE_131` 指向两批原始导入清单。具体配置见 [接入说明](../competition-search-handoff.md)。

数据库测试覆盖三批原包及成品覆盖文档的预演回滚、重复导入、草稿隔离、审核后查询、撤下后立即停止返回。核心测试覆盖字段信息不足、资格冲突、时间边界、正文变更、索引过期、模型缺失、损坏索引与真实赛事卡片适配。

阅读版已通过浏览器搜索、展开、章节和来源检查；历史赛事标题及跨届资源修复后再次验证。CSV 198 行、11 列经 Artifact Tool 导入、回算、渲染及序列化比较，内容相同，预览无截断。该辅助 Node 进程在打印完成信息后返回 1 且未给诊断，因此不计作通过的自动化命令；CSV 字节一致性由独立重建检查确认。

## 修改范围与审查重点

| 文件或目录 | 修改目的 |
| --- | --- |
| `backend/curation/product.py`、`test_product.py` | 共享成品转换、事实与过程说明分离、规则回归 |
| `backend/information_library/competition_search.py`、`semantic.py`、`test_competition_search.py` | 检索、字段匹配、理由、数据库适配、索引与异常回归 |
| `backend/curation/test_knowledge_delivery.py` | 实包、审核和撤下的隔离集成验证 |
| `backend/requirements-retrieval.txt` | 独立语义环境依赖固定版本 |
| 三个原有资料生成器 | 复用共享正文转换；原始底稿保留 |
| `scripts/build-competition-knowledge.py`、`build-knowledge-imports.py` | 重建公开资料与兼容 curation 的三个导入包 |
| `scripts/competition-search.py`、`prepare-competition-model.py` | 独立演示、模型准备和索引构建 |
| `scripts/audit-competition-sources.py`、两个知识检查脚本 | 来源访问记录、质量检查与重建验证 |
| 三个评测脚本及 `docs/competition-evaluation/` | 题目、标准依据、运行工具、冻结历史与对比报告 |
| `docs/competition-knowledge/`、本维护目录 | 成品与维护材料分开交付 |
| `README.md`、`docs/progress.md`、接入说明 | 成果入口、当前状态及队友调用约定 |

简洁 diff 摘要：新增知识转换、检索和评测三部分；三个旧生成流程桥接统一正文；新增 11 个成品文件、三个导入包及版本化证据和评测文件。未新增数据库迁移，未更改聊天界面或问答 API。

重点审查：67 项内部处理结论；报名窗口、专业及年级覆盖；真实学校赛事名称与官方域名的保留是否符合比赛展示要求；邀请制、院校推荐等正文限制；队友对 `knowledge_results`、`passages`、`empty_result` 的接入。日期判断按日，官方精确时刻保留在正文。

实现验收时，Git 工作区包含用户已有未提交修改和本轮新增内容，尚未执行 `git commit` 或 `git push`。当时的本地状态日志未纳入交付包；后续交付以交付分支和提交记录为准。
