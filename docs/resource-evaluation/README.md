# 学习资源问答检索回归

此评测直接读取当前配置的 PostgreSQL 公开资源，通过真实 `_prepare_chat` 检查最终交给问答模型的来源、推荐卡和赛事关联上下文。不生成回答，不调用收费模型、不联网搜索、不下载 embedding 模型；已有本地 BGE 与索引可按当前配置运行。

`cases.json` 包含 16 条 2026-10-10 实测问题（14 正例、2 指名资料缺失负例）、修复时独立设计的 10 条新问法，以及审查新增的“CS9999 + Python”混合标识符负例，共 27 题、双模式 54 次。判断来自当时全部 322 条公开资源，文件仅保存涉及的 34 条公开资料证据（目标及已审查的偏题项），不把完整数据库或本机日志提交。测试时不隔离或缩小候选库，使用当前数据库全部可公开资源；新增资源不会因为数量超过 322 而失败。

10 条新问法用于独立泛化验证，没有未经修改实现上的修前成绩。最后两条覆盖 PubMed 检索帮助文档及 OpenCV 阈值分割教程。修复中途运行所得报告只能称“中途检查”，不能标成修前基线；原始 16 条真实回答才有此前记录。

## 运行

先按 [后端开发文档](../backend-development.md) 配好已有数据库和依赖。无需配置 `AI_CHAT` 或 DeepSeek 等模型密钥。以下从仓库根目录运行，Python 路径替换为本机已有 Django 虚拟环境：

```powershell
# 默认当前本地检索配置，分别覆盖 smart 与 resource。
.\backend\.venv\Scripts\python.exe scripts\evaluate-resource-chat-retrieval.py `
  --mode smart --mode resource `
  --output .local\resource-evaluation\configured.json

# 只在本次进程临时关闭语义索引，检验无索引时的回退行为。
.\backend\.venv\Scripts\python.exe scripts\evaluate-resource-chat-retrieval.py `
  --mode smart --mode resource --keyword-only `
  --output .local\resource-evaluation\keyword.json

# 单独运行新增表达；也可用 --case 指定一个或多个完整 case ID。
.\backend\.venv\Scripts\python.exe scripts\evaluate-resource-chat-retrieval.py `
  --split generalization --output .local\resource-evaluation\generalization.json
```

不传 `--mode` 时仅运行 smart。退出码 `0` 表示全部所选检查通过，`1` 表示检索或外部调用防护检查失败，`2` 表示样本前提已过时（例如预期资源已下架，或负例资料后来确实入库）。数据库配置等执行错误也会返回非零，不视为通过。

本机已配置语义索引且本次需要验收该配置时，加 `--require-semantic`：要求统一索引配置存在、至少一题实际使用 hybrid，且所有题无检索回退 warning。该参数不能与 `--keyword-only` 同用。少量明确缺失资料仍可能正常使用 keyword/空结果，不要求每题都出现语义结果。

脚本在 PostgreSQL `READ ONLY` 事务中执行并回滚，只写指定报告文件。它阻断聊天客户端和 HTTP 调用，强制 Hugging Face 离线；默认保留本地索引配置，`--keyword-only` 仅临时覆盖本进程环境，不修改 `.env`。模型或索引缺失时遵循产品的回退行为，报告保留实际 `retrieval.warnings`，不能把 `current_local_configuration` 标签误读为已成功使用语义检索。

## 独立判定

- **目标命中：**每个正例的人工允许 ID 集合，必须至少有一个同时进入最终 `sources` 和 `recommendations`。不检查中间 top-k，以免资源在来源预算、类型筛选等后处理时丢失还被算通过。
- **公开身份：**返回的资源 ID 和标题必须对应当前公开可用数据库记录；推荐卡需有最终来源和入口。负例不许凭空生成指定课程/作者资料身份，允许明确的相关替代。指名缺失的 CS231n 不应带其他推荐；“只要 CS9999 的 Python 教程，不要其他课程”必须无来源和推荐，不能用已知 Python 关键词绕过未知课程标识符。
- **明显偏题：**RM 问法不能带 Formula/方程式或 Fiji/ImageJ；CSES 问法不能带数据新闻、影视、汇创青春、学院奖赛事。这些是人工负相关判断，不复用生产排序、别名或打分逻辑。
- **同类型的偏题资源：**检查资源 ID 的人工负相关判断，不因都是 `resource` 就放行。Python基础请求排除视觉、仿真、生物科研技能及标注资料；明确拒绝通知的蓝桥问题排除规程/报名材料；高教社杯国赛题排除美赛、ICPC、笔译及增减材赛项文件；回归诊断示例排除表格筛选基础教程与比赛通知。每题 `precision_judgment` 说明理由，`resource_evidence` 保存这些资料真实标题、描述和出处。
- **不过度限制补充：**不强制所有查询仅返回目标 ID。JupyterLab 可以补充运行诊断 notebook，jamovi/Orange 属于同主题统计分析工具，OpenCV通用教程可补充图像阈值分割。精度检查只覆盖已作人工判断的错误项及明确类型范围，不能把没有被禁止的结果全部宣称为精准。
- **推荐范围：**新增问法明确要资料/工具，推荐卡允许资源类型；题中直接点名 RoboMaster、CCPC、美赛时，也允许该项赛事卡作补充，但不能扩展成其他赛事推荐。报告另列全部非目标卡片、精度失败项及 `precision_failed_runs`，便于人工复核，不能只看目标命中率。
- **蓝桥杯关联：**从当前数据库目录绑定求真实赛事 ID，核对最终上下文中 Python 资源的外键关系，并要求“蓝桥杯”名称可见。只给无法解释的数据库编号不足以防止回答误称“未关联”。

新增问法覆盖 Python 文件读写、RoboMaster C 型开发板、CCPC 作业与证明、美赛数组广播、Zotero AI 技能、问卷回归 notebook、CSES 题库、`.bib` 自动同步、PubMed 检索指南、OpenCV 阈值分割。不要因为某条失败就把新问法或期望改成实现恰好支持的表达；先核实公开证据和用户意图，再修复问题或说明限制。

报告记录数据库公开资源数量及指纹、fixture 哈希、主要实现文件哈希、模式和每题最终结果，方便区分中途状态与最终验证。若运行期间主要实现文件变化，返回非零，需等代码稳定后重跑。运行时日志放 `.local/`，不提交包含环境信息的调试记录。

## 边界

这个免费回归不证明生成的自然语言答案准确，也不检查正文 URL 清理结果或前端点击效果。“负例通过”仅证明准备阶段没有伪造返回资料身份；“入口存在”仅指响应字段有链接。真实回答仍应人工检查是否把“本轮未找到”说成“平台没有”，以及是否正确表达赛事关联、保留已有资料入口。

例如首次实测中 Python 教程已经进卡片，但正文错误否认蓝桥关联；Zotero 已命中，但正文入口变成“未经核实的链接已省略”。只统计目标 ID 命中会掩盖这些问题。
