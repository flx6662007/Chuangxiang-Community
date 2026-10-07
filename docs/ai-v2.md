# 创享 AI 助手

首页赛事助手完成需求输入、条件理解、赛事检索、资料分析、条件判断和现有招募查询。当前操作入口、接口和验收步骤见[赛事助手接入](ai-assistant-handoff.md)。

赛事知识统一使用 `information_library.competition_search.search_competitions`，支持关键词、BGE 语义和混合检索。`ai_services/competition_knowledge.py` 将段落及其来源适配给通用聊天；`ai_services/guide.py` 保存用户条件并连接现有招募。

旧 E5 检索实现已移除。历史 `KnowledgeChunk` 表与迁移保留，当前运行不读取它；`rebuild_ai_index` 构建统一 BGE NPZ 索引。`prepare-ai-embedding.py` 兼容旧命令名称，实际调用 `prepare-competition-model.py`。

通用聊天支持学习资源和登记官网查询；科研查询由 `PUBLIC_RESEARCH_ENABLED` 控制，当前默认关闭。聊天使用原有 `/api/v1/ai/chat/` 消息契约。所有赛事知识读取当前公开版本，资料内的历史届次和时间继续保留。

## 科研结构化资料接入（2026-10-07）

首页“科研”栏目和智能模式的科研问题已使用同一条 RAG 链路：公开数据库资料 → 字段关键词与 BGE 混合检索 → 按字段组装来源 → DeepSeek 自然语言回答。页面上的普通搜索仍用于浏览卡片。队长的内测网站需单独导入并配置，本机修改不等于内测部署。

`research/knowledge.py` 将卡片的学校、简介、方向、地点、成果，以及招募对象、申请条件、参与工作、时间投入、范围、批次、截止和状态转换为公共事实。未填字段不补写；联系资料与内部审核记录不进入上下文。每个事实使用 `fieldLinks` 中已核验的对应来源；介绍、成果、招募分别形成片段，保留章节锚点。仅有链接没有整理正文时，只作为阅读入口，不视为已读取完整论文。

检索保持关键词 + BGE + RRF；新增科研自然语言词处理、明确学校约束、角色／兼职／跨校资格筛选和有名称的实验室追问。本科在读与本科学历、博士生与博士后分别判断；不知道校外资格时不命中跨校条件。普通招募推荐排除已结束和历史批次；点名实验室时保留原始条件以回答资格问题，历史信息带状态。介绍性问题中的读者学历不会自动变成申请限制。当前是规则识别，复杂否定、多实验室指代及任意口语表达仍需继续扩充评测。

回答最多使用 6 个来源，研究介绍、成果与招募可各占一个；多个实验室先各取一个相关片段。相关推荐同时返回 `facts`、`field_links`，前端沿用科研卡片的字段链接组件，并保留“官方说明”。通用聊天仍受原有 CSRF、限流和模型错误处理约束；没有配置模型时显示普通检索降级界面。

### 资料更新与索引

全国包新增按稳定编号对应的 `sources` 元数据，数据库导入将已读补充网页写入现有 `ResearchSource`，主链接不重复建行。补充来源变化产生 `ResearchRevision`；预演回滚、重复导入不变、更早未入包的记录保留。当前 120 条资料、9 条补充来源，不混入同济资料。

在仓库根目录、已配置数据库的 Python 环境执行（首先预演，确认后再应用）：

```powershell
python scripts/build-national-research-package.py --check
python backend/manage.py import_research_materials --source docs/research-national/20261007/research-cards.json --database --publish
python backend/manage.py import_research_materials --source docs/research-national/20261007/research-cards.json --database --publish --apply
python -m pip install -r backend/requirements-retrieval.txt
python scripts/prepare-competition-model.py
```

在本机 `backend/.env` 设置 `PUBLIC_RESEARCH_ENABLED=1`、现有 `DEEPSEEK_*`，并将 `COMPETITION_EMBEDDING_MODEL_PATH` 指向模型目录的绝对路径、`UNIFIED_SEMANTIC_INDEX` 指向科研／资源 NPZ 的绝对路径，然后运行：

```powershell
python backend/manage.py rebuild_unified_index
python scripts/evaluate-research-search.py --output .local/research-national/ai-review/evaluation.json
```

更新 `.env` 后需重启后端。现有赛事使用独立 `COMPETITION_SEMANTIC_INDEX`，不要替换成科研索引。统一索引升级为 schema 2，片段附字段、来源和版本；字段、来源核验或发布状态变化后旧索引失效，自动用关键词检索，并重新分配评分权重。需要重新执行 `rebuild_unified_index` 恢复语义检索。模型和索引均保留本机，不能提交。

固定评测题见 [30 道科研检索问题](research-national/ai-retrieval-evaluation.json)。本机 120 条资料测试：22 道定向题的前五条命中，旧字段关键词基线 15/22，新增字段关键词及实际 BGE 混合检索均为 22/22；8 道条件检查通过，结果无重复。此结果是该固定题集上的回归结果，不代表所有自然语言查询的准确率。
