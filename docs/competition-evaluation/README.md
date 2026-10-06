# 赛事检索评测集

第一版固定 150 道题，覆盖 60 个赛事系列：开发集 100 题，验收集 50 题。每个知识问题族包含一条明确赛事名称的问题和一条实质需求改写；同一赛事系列的全部题目只属于一个集合。

题目与标准依据先按三批整理资料编写，再绑定正式知识包的记录和证据标识。构建脚本不调用检索，也不根据检索命中结果增加标准答案。`questions.tsv` 保存 60 个知识问题族；构建脚本保存另外 15 个资格、人数、日期和资料缺失问题族。对应的 JSONL 每行是一道可独立运行的题。

| 文件 | 内容 |
| --- | --- |
| `dev.jsonl` | 100 道开发题，用于检查规则和比较召回方案 |
| `test.jsonl` | 50 道冻结验收题，用于确定方案后的最终报告 |
| `manifest.json` | 语料版本、文件 SHA-256、题型与系列数量 |
| `questions.tsv` | 问题、语义改写、标准事实及来源定位锚点 |
| `negative-probes.json` | 2 道不锁目录、没有相关主题的独立开发诊断，不计入冻结的 150 题 |
| `calibration/` | 开发集各轮阈值、空主题诊断的完整报告，以及对应开发题快照 |
| `dev-report.json`、`test-report.json`、`probe-report.json` | 对应运行环境下的三种检索模式实测结果 |
| `REPORT.md` | 实测对比、阈值依据、失败案例及适用范围 |
| `history/` | 资料修正前已执行的验收报告与题集，不覆盖先前结果 |

每题包含 `query`、`filters`、`preferences`、`as_of`、`relevant_ids`、`evidence_ids`、`expect_empty`、`group`、`split`、`scenario`，并附 `gold_statement` 与 `gold_references`。后两项保留依据片段、来源网址和位置，供复查相关性判断。来源片段是整理摘要；没有原文引句时不将摘要标成原文引用。

已知正例是问题明确描述的目标赛事，不是对整个互联网的穷尽相关性标注。30 道约束题包含 10 道满足条件的正例和 20 道应为空结果的负例，覆盖人数上下界、学历、个人／团队、报名窗口、历史赛季和必要条件缺失。约束题以目录范围锁定目标赛事；同一问题族尽量使用正反条件对照，避免全部拒绝的实现获得好成绩。另有 120 道知识问题，包含名称与简称、历史规则、语义改写及多字段筛选，其中 60 道为语义改写。合计 130 道有答案题、20 道空结果题。

## 运行

以下命令在仓库根目录执行；运行三种模式时使用已安装语义依赖且模型已准备完成的 Python 环境。

```powershell
$env:COMPETITION_EMBEDDING_MODEL_PATH = (Join-Path (Get-Location) '.local/models/bge-small-zh-v1.5')
python scripts/build-competition-evaluation.py --check
python scripts/test-competition-evaluation.py
python scripts/evaluate-competition-search.py --split dev --index .local/competition-search/index.npz --semantic-threshold 0.60 --output docs/competition-evaluation/dev-report.json
python scripts/evaluate-competition-search.py --probes docs/competition-evaluation/negative-probes.json --index .local/competition-search/index.npz --semantic-threshold 0.60 --output docs/competition-evaluation/probe-report.json
python scripts/evaluate-competition-search.py --split test --index .local/competition-search/index.npz --semantic-threshold 0.60 --output docs/competition-evaluation/test-report.json
```

只检查关键词模式时可省略索引，并传入 `--modes keyword`。`--corpus`、`--fixtures` 和 `--index` 可指定其他数据位置。开发集可传入 `--semantic-threshold` 比较阈值；选定后保持该值运行验收集。首轮生成 JSONL 使用 `python scripts/build-competition-evaluation.py`；已有文件需要更新时，必须明确传入 `--update-fixtures`，复核证据变化并保存新的版本报告。

验收集在检索运行前冻结。仅用开发集选择检索阈值和规则；验收失败仍记录真实结果，不利用验收题调参后重新宣称首次验收通过。资料事实更新需要新的语料版本和新的评测版本，旧报告保留原版本号，不能混用。

文本哈希按 CRLF 转 LF 后计算，允许 Windows 与其他系统使用不同换行符，题目和证据内容的变化仍会触发校验失败。

阈值选择同时查看开发集召回和独立空主题诊断。诊断问题为真实宠物犬的敏捷障碍赛、职业扑克现金赛，均不传目录筛选；已核对当前语料没有这些赛事主题。它们用于发现通用词误匹配，不能替代覆盖更多领域的相关性标注。语料后来收录相关主题时，运行器会要求重新审查诊断题。

## 指标解释

- **Hit@5：**有答案题中，前 5 条至少包含一条标注目标的比例；运行错误仍计入分母。
- **语义改写 Hit@5：**只统计语义问题，分别报告三种模式及混合检索相对关键词的差值。
- **空结果准确率：**20 道负例中正确返回空结果的比例；模型报错不算正确拒绝。
- **空结果说明覆盖：**正确为空的回答必须返回原因代码与文字；有显式筛选条件时，说明须包含这些条件的字段和值。报告保存实际说明，便于检查“不满足”和“信息不足”的解释。
- **硬条件违规数：**评测器独立检查返回记录及其证据，不复用被测筛选函数。缺少必要字段或字段证据也记违规。
- **证据引用覆盖：**理由引用的证据须真实存在于对应记录，且实际随结果返回。该指标检查引用链，不能代替逐条判断“证据是否支持完整表述”。另报告目标证据命中率，便于发现赛事找对、依据找错的情况。
- **耗时：**逐次调用记录毫秒数，报告中位数、P95 和最大值。首次模型载入可能计入首个请求；不把不同机器结果当作严格性能对比。

命中率目标为至少 90%，硬条件违规为 0，空结果准确率为 100%，理由证据引用覆盖为 100%。三模式运行以混合检索为验收对象，其整体命中率还应不低于关键词模式；关键词与纯语义模式作为对照报告。只运行一种模式时，对该模式应用指标门槛。命令退出码 `0` 表示验收对象达标，`1` 表示运行完成但指标未达标，`2` 表示存在模型、索引或查询执行错误。模型缺失导致的混合降级单独记为运行错误，不能报告为混合检索成功。

当前题集用于检索与匹配验收。大模型生成回答的完整事实一致性、用户语言多样性和线上使用频率分布，需要在问答 API 接入后另设评测；本报告不以检索命中率代替问答质量。

## 2026-10-06 日期字段补充

语料更新为 `d744beaf5c993b25`。根据原始依据重新绑定后，100 道开发题、50 道验收题及其标准片段逐字节不变，仅更新 manifest 的语料版本。新增组队规则由 `competitions.test_recruitment_policy`、`curation.test_activation` 和组队流程测试覆盖；本评测集继续评价原届次知识检索与官方资格条件。

本轮实测：开发集混合 Hit@5 为 98.89%，冻结集为 100%，硬条件违规均为 0。冻结集纯语义 Hit@5 为 80%。完整报告见 [开发集](runs/2026-10-06/dev-report.json) 与 [冻结集](runs/2026-10-06/test-report.json)。
