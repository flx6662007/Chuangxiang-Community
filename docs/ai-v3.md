# 科创 AI 助手 V3 接入说明

首页共用 `/api/v1/ai/chat/`。请求仍提交交替的 `messages`，可增加 `mode`：`smart`（缺省）、`competition`、`research`、`resource`。回复继续返回 `message`、`sources`、`route`、`retrieval`，并增加 `mode` 和 `recommendations`。切换模式会开始新对话，赛事模式的原有赛事向导保留。

检索先通过公开状态筛选。赛事沿用已编审资料的关键词/BGE/RRF 检索，也纳入直接发布的赛事；资源只取 `published + available`；科研机会须设置 `PUBLIC_RESEARCH_ENABLED=1`，且有已核验的公开来源。资源关系直接读取 `ResourceCompetition` 和 `ResourceResearchOpportunity`。推荐结果包含对象类型、编号、理由、关联资源、来源与核验状态。`research_group` 文本只作科研机会的原文展示，不产生课题组实体。

资源与科研的向量索引使用现有 BGE 模型与本地 NPZ 文件，不需要 Qdrant。设置 `UNIFIED_SEMANTIC_INDEX` 后，在 backend 目录运行 `python manage.py rebuild_unified_index`，资料更新后重建。模型路径沿用 `COMPETITION_EMBEDDING_MODEL_PATH`。未配置、过期或模型不可用时回退关键词；赛事索引仍由原有流程维护。排序权重集中在 `ai_services/unified.py`，可由 Django 的 `AI_RETRIEVAL_WEIGHTS`、`AI_RETRIEVAL_BASELINES` 覆盖。外搜阈值可由 `AI_EXTERNAL_SEARCH` 的 `MIN_RESULTS`、`MIN_CONFIDENCE` 覆盖。

外部检索由 `ai_services/web.py` 的 adapter 接口承载。当前仅接入已登记的官方赛事站点，且只读取可识别的通知页；没有部署 SearXNG，也没有通用搜索 API。显式要求官网/最新信息、时效性问题、站内结果不足或置信度不足时才尝试外部检索。普通 adapter 返回的网页默认标为未经人工审核的 Web 补充，不能自称官方。未来接入 SearXNG 或其他 API 时，须在服务端核验来源域名与类型，再提升信任等级。`read_at` 只表示读取时间，不代表原文发布日期。

未来 ResearchGroup selector 的每条记录应提供稳定 `object_id`、`object_type=research_group`、`title`、`summary`、`content`、公开 `source_url`、`version`、`status=published`、`verified_at`；建议同时提供 `published_at`、机构、研究方向、分类与标签。若需课题组 ↔ 资源/科研机会关联，应提供真实外键或经审核的稳定关联 ID，供 `related_object_ids` 使用。数据库负责人还需明确撤下状态、内容版本、来源审核人与审核时间、对外可见范围，以及来源变更后的索引失效规则。
