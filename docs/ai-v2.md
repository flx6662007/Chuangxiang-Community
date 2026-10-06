# 创享 AI 助手

首页赛事助手完成需求输入、条件理解、赛事检索、资料分析、条件判断和现有招募查询。当前操作入口、接口和验收步骤见[赛事助手接入](ai-assistant-handoff.md)。

赛事知识统一使用 `information_library.competition_search.search_competitions`，支持关键词、BGE 语义和混合检索。`ai_services/competition_knowledge.py` 将段落及其来源适配给通用聊天；`ai_services/guide.py` 保存用户条件并连接现有招募。

旧 E5 检索实现已移除。历史 `KnowledgeChunk` 表与迁移保留，当前运行不读取它；`rebuild_ai_index` 构建统一 BGE NPZ 索引。`prepare-ai-embedding.py` 兼容旧命令名称，实际调用 `prepare-competition-model.py`。

通用聊天支持学习资源和登记官网查询；科研查询由 `PUBLIC_RESEARCH_ENABLED` 控制，当前默认关闭。聊天使用原有 `/api/v1/ai/chat/` 消息契约。所有赛事知识读取当前公开版本，资料内的历史届次和时间继续保留。
