# 科创 AI 助手接入说明

更新至 2026-10-10 的代码状态。首页支持智能、赛事、科研、资源四种模式，包含多轮理解、公开资料检索、流式回答和可选联网搜索。赛事向导继续提供找赛事、分析适配与找队友流程。实现与历史验收见[赛事助手交接](ai-assistant-handoff.md)、[科研交付](releases/research-ai-20261007.md)及[多轮与联网交付](ai-optimization-20261008.md)；这些记录不证明目标环境已经部署。

## 请求与会话

| 入口 | 行为 |
| --- | --- |
| `POST /api/v1/ai/chat/` | 返回完整 JSON：`message`、`sources`、`recommendations`、`mode`、`route`、`retrieval`、`conversation_context` |
| `POST /api/v1/ai/chat/stream/` | 首页使用的 SSE 入口；最终 `done` 携带完整结果，原 JSON 接口保留 |
| `GET/POST /api/v1/ai/guide/` | 恢复或操作赛事向导，使用 7 天 Session；与通用聊天签名上下文分开 |
| `GET /api/v1/ai/search/?q=...` | 无模型的公开目录及正文关键词搜索，供普通检索使用 |
| `GET /api/v1/ai/status/` | 检查聊天配置格式；`chat_configured=true` 不代表密钥、余额或网络已通过真实调用 |

两种聊天接口提交交替的 `messages`，可携带 `mode`（`smart`、`competition`、`research`、`resource`）、上一成功回答的 `conversation_context` 和布尔值 `web_search`。游客可使用，POST 仍须 CSRF 校验；聊天按来源 IP 限流。切换模式开始新对话。

多轮理解复用聊天模型，结合最近历史与服务器签名状态生成独立检索问题；涉及历史理解时会增加一次模型调用。签名有效期 24 小时，绑定模式，多进程须共用 Django `SECRET_KEY`。历史回答不能代替本轮重新读取的公开事实。

流式事件为 `status`（`retrieving` / `generating`）、`delta`、`done` 或 `error`。前端仅在 `done` 接受最终引用、推荐和上下文；停止、异常或迟到响应不写入成功历史，重试不重复提问。生成中的正文链接在最终校验前不可点击。

## 资料与索引

赛事使用已编审公开资料的关键词/BGE 混合检索，也读取直接发布的赛事；资源只取 `published + available`。科研须设置 `PUBLIC_RESEARCH_ENABLED=1`，再读取具有核验依据的公开资料。科研介绍、成果与招募分别取证，资格不明确时保留待确认说明。资源关系读取 `ResourceCompetition`、`ResourceResearchOpportunity` 及当前有效资料版本的赛事目录关联，公开队伍推荐不暴露成员或联系人资料。

资源查询同时匹配名称、内容与已关联赛事，中文按短语匹配，英文使用词边界和名称简称，避免把 RM 匹配到 Formula。教程、习题、规则、赛题、插件等需求进入资料检索；资源模式不混入赛事或队伍推荐。返回上下文保留关联赛事名称，来源预算按检索顺序分配。资料中登记的项目主页、文档等入口随 `sources[].links` 返回；来源和推荐标题打开站内详情，外部入口单独保留。

| 索引 | 配置与重建命令（在仓库根目录运行） |
| --- | --- |
| 赛事公开正文 | `COMPETITION_SEMANTIC_INDEX`；`python backend/manage.py rebuild_ai_index` |
| 资源与科研 | `UNIFIED_SEMANTIC_INDEX`；`python backend/manage.py rebuild_unified_index` |

两份 NPZ 使用 `COMPETITION_EMBEDDING_MODEL_PATH` 指定的固定版本 BGE 模型，互不替换，不需要 Qdrant。先安装 `backend/requirements-retrieval.txt`，必要时运行 `scripts/prepare-competition-model.py`，再从目标数据库的公开资料重建。统一索引使用 schema 3，包含资源的赛事目录名称与关联信息；旧 schema 2 须重建。未配置、过期或模型不可用时降级关键词，赛事索引可用不代表资源语义检索已启用。资料、来源、关联或发布状态变化后需重建，科研关闭时不会进入该索引的公开资料集合。模型和索引放被 Git 忽略的本机目录。

资源索引可写到仓库内 `.local/unified-search/database.npz`：

```powershell
python backend/manage.py rebuild_unified_index --output .local/unified-search/database.npz
```

将该文件的**绝对路径**写入本机 `backend/.env` 的 `UNIFIED_SEMANTIC_INDEX`，重启后端，再按[学习资源检索回归](resource-evaluation/README.md)验证。报告应无 `unified_index_unconfigured` / `unified_index_stale`；仅执行构建命令或设置路径都不等于问答验收通过。

排序设置位于 `ai_services/unified.py`，可通过 Django 的 `AI_RETRIEVAL_WEIGHTS`、`AI_RETRIEVAL_BASELINES` 覆盖。科研数据导入、开关及字段证据维护见[科研交付](releases/research-ai-20261007.md)和[AI 维护说明](ai-v2.md)。

## 可选联网搜索

`web_search=false` 禁止站外调用；新前端默认发送此值。`true` 对非闲聊问题请求外部补充；省略时兼容原有按用户意图、结果数量和置信度决定的自动策略，不能把省略视为关闭。

`ai_services/web.py` 保留登记官网适配器；配置 `AI_SEARXNG_URL` 后另启用 SearXNG。Windows 本机启动、容器地址与服务器部署步骤见[联网配置](ai-optimization-20261008.md#配置与启动)。仓库提供启动配置，不会随拉取代码自动启动搜索服务。

搜索摘要只用于发现网页，读取成功的正文才可作为回答证据。SearXNG 正文读取默认最多 3 页、共享 15 秒预算，成功结果缓存 5 分钟。登记官网或服务端明确配置的官方域名可获官方标签，其余标为 Web 补充；站外来源不冒充人工核验，`read_at` 仅是读取时间。阈值和官方域名映射由 Django `AI_EXTERNAL_SEARCH` 控制。

## 配置、验收与扩展边界

首页聊天与向导使用服务端 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`；内部草稿服务的 `AI_ENABLED` 不控制这些入口。配置分类见[AI 服务](ai-services.md)。目标环境需完成依赖、数据库迁移、资料导入、模型与索引、前端构建、服务重启和实际回答验收；Git 不同步真实数据库、密钥或运行服务。

已有固定检索题集、离线回归及历史真实模型验收记录，各自只证明对应范围，不等于任意问题准确率。上线前仍须检查科研开关、来源、时间与资格说明、流式停止/重试，以及联网开关实际行为。

当前 `research_group` 是科研机会的原文标签，不生成独立课题组实体。`ResearchGroupSelector` 是返回空列表的扩展接口：将来接入时须提供稳定 `object_id`、类型、标题、摘要、正文、公开来源、核验时间、版本及发布状态；关联须来自真实外键或审核后的稳定 ID，并明确撤下与索引失效规则。不能把这个接口写成已完成课题组数据库。
