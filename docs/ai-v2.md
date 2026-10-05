# 创享 AI V2：多源可信检索（开发说明）

2026-10-04 至 10-05。首页仍通过 `POST /api/v1/ai/chat/` 发送 V1 的交替 `messages`，仍使用服务器端 `DEEPSEEK_*` 配置。响应保留 `message`，增加 `sources`、`route`、`retrieval`。前端只把 `role/content` 送回下一轮；来源和状态仅供展示。普通请求不写业务对象，不访问账号联系方式，不执行工具调用。

## 实际覆盖与边界

1. 路由按关键词确定 `general/platform/knowledge/web/hybrid` 与 `competition/project/resource/team/other`。不另付费调用 LLM 分类。当前未识别的复杂语义按普通问答处理，不能作为检索命中依据。
2. `PLATFORM_CONTEXT` 复用 `information_library.selectors.collect_records()` 的公开赛事与科研记录；赛事遵守 `COMPETITION_CATALOG_ONLY`，项目 JSON 只返回官方原文链接且提示名额待确认。资源仅来自真实数据库中已发布、可用、核验过的 `Resource`，当前前端 15 条 Mock 不进入 AI。赛事的站内详情为 `/competitions/:id`；资源前台仍是 Mock，因此资源来源只链接真实访问地址。
3. `KNOWLEDGE_CONTEXT` 仅取 `student_visible_documents()` 当前审核版本、带公网来源和可读正文的 chunk。当前库已审核文档为 0，真实回复会写明“暂无已审核知识资料”，不能称作真实 RAG 命中。草稿包、未审核 OfficialNotice、未解析附件不会自动公开。附件没有可靠页码映射时不展示页码。
4. `WEB_CONTEXT` 只在明确要求官网、最新公告或联网时启用。从启用的 `OfficialSite` 中按赛事名称匹配一个入口，使用现有 `OfficialClient` 的白名单、robots、DNS/私网、重定向、TLS、大小和超时限制读取一页；普通入口页不冒充独立通知，robots 要求等待超过 5 秒时跳过本次聊天读取。不接受用户 URL，不做开放网络搜索、不存网页、不改变发布状态。来源标记“未经人工审核”。没匹配或网络失败时如实显示覆盖限制。
5. 来源由服务器根据真实检索结果编号并返回。上下文最多 6 条、正文约 7500 字；模型输出中的未知编号与非来源 URL 会被移除。旧平台记录与新官网网页如内容不同会并列给出日期；不能把截止未知写作正在报名。无来源的事实类请求由服务器返回明确的未查到说明，不让模型猜测。

## API 响应

```json
{
  "message": {"role": "assistant", "content": "..."},
  "sources": [{"id": 1, "kind": "competition", "entity_id": "db-12", "version": "...", "title": "...", "url": "https://...", "internal_url": "/competitions/12", "verified_at": "...", "published_on": null, "status": "unknown", "status_note": "..."}],
  "route": {"intent": "platform", "domains": ["competition"], "current": false, "web_requested": false, "knowledge_requested": false},
  "retrieval": {"knowledge": "not_requested", "web": "not_requested", "has_sources": true}
}
```

来源 URL 仅为后端核验的公网 HTTP(S) 地址；`internal_url` 只允许真实公开赛事详情。`read_at` 仅用于刚读取的官网页，`locator/edition` 用于已审核知识。失败仍沿用 V1 固定错误代码、CSRF 和每 IP 每分钟 10 次限流。

## Embedding 与数据库

新增 `curation.KnowledgeChunk` 迁移。向量以 PostgreSQL JSON 列持久化，按当前可见文档做最多 2000 chunk 的精确内存余弦排序；当前无 pgvector 扩展，也没有近似索引或独立向量库。每行保存文档、当前 revision、内容哈希、位置、来源 URL、模型 ID/revision/384 维向量。查询时重查审核状态、当前版本、关联资源/赛事状态与正文哈希；撤下立即不可见。管理员审核或版本变化后显式重建：

```bash
cd backend
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py rebuild_ai_index
```

`rebuild_ai_index` 在编码成功后事务替换旧索引；空审核语料会删除旧索引并写 0 条。只对 `DocumentRevision.body` 的已审核可读文本切分；不会从搜索结果链接或扫描件猜正文。当前版本没有段落到多个 URL 的来源映射，因此多 URL 正文不入索引，避免把片段错归给第一条链接。chunk 的 `locator` 沿用资料来源定位，不能据此推断 PDF 页码。

候选模型为 [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)：MIT、384 维、约 471 MB 权重，支持中英混合。查询与正文分别加 `query:` / `passage:`。与 [BGE-M3](https://huggingface.co/BAAI/bge-m3)（MIT、1024 维、长文本能力更强，模型明显更大）相比，本轮小库优先考虑磁盘和 CPU 成本。当前 Mac 未安装权重和依赖，且真实审核语料为空，因此**尚未用真实标注题评测两模型、测 Mac 推理时延或确定最终模型**；不能把隔离夹具结果说成真实准确率。上线知识检索前需先批准文档，制作中文、英文、中英混合标注问题，比较召回、误命中、首次载入和 P95 延迟，再决定是否沿用 E5 或重建为其他模型。

候选模型准备是显式运维步骤，不发生在聊天请求里：

```bash
cd backend
./.venv/bin/python -m pip install -r requirements-embedding.txt
./.venv/bin/python ../scripts/prepare-ai-embedding.py
export AI_EMBEDDING_MODEL_PATH="$PWD/../.local/models/multilingual-e5-small"
./.venv/bin/python manage.py rebuild_ai_index
```

准备脚本固定模型 revision 并写入清单；运行时仅离线加载清单匹配的本地模型。模型改变须重新评测并重建索引。部署时 `DEEPSEEK_*` 已在 `compose.yaml` 转发；可设置 `AI_EMBEDDING_INSTALL=1` 构建可选依赖，并将准备好的模型放在 `AI_EMBEDDING_MODEL_DIR/multilingual-e5-small`。部署需先跑迁移、再显式建索引；本轮未部署。

## Checkpoint 验证记录

| 阶段 | 本轮修改 | 已执行验证 | 仍需人工检查 |
| --- | --- | --- | --- |
| A | 路由、公开平台检索、目录范围修正 | `manage.py test ai_services information_library`：65 通过 | 真实公开库为空；导入后核查排序与来源 |
| B | 可撤回 chunk 索引、离线模型候选、审核边界 | `manage.py test ai_services curation information_library`：104 项，101 通过、3 项原有跳过 | 真实审核语料/模型基准、服务器模型安装 |
| C | 登记官网单页读取 | 同一隔离测试：107 项，104 通过、3 项原有跳过 | 不同官网的 robots、动态网页、超时与访问稳定性 |
| D | 来源合成、结构化响应、前端展示 | 隔离后端 145 项，142 通过、3 项原有跳过；前端 51 项通过；Vite 构建成功。本机真实 DeepSeek 普通聊天与登记官网问答均 HTTP 200，后者返回 1 条 Web 来源 | 浏览器手工查看移动端、实际资料审批后的 RAG 准确率 |

开发库已应用 `curation.0003`，执行重建得到 0 条审核 chunk。没有在生产库执行迁移或部署。曾尝试把依赖 PostgreSQL 来源级互斥的整个 `ingestion.tests` 套件放在 SQLite 隔离库运行，出现 5 个数据库特性错误与 1 个互斥测试失败；另发现 1 个新网页夹具正文太短，修正后重新运行通过。随后只运行 HTTP 安全相关的 `ingestion.tests.AdapterTests`。独立 PostgreSQL 测试库复核也已尝试，因当前数据库用户没有创建 `test_chuangxiang_dev` 的权限，在运行用例前停止；没有把开发库当测试库。完整采集回归仍需预建独立测试库。

## 开放网络搜索：等待 Provider 选择

当前实现不发现登记范围外的网站。若要增加站外发现，需要独立 Search API 账号与 Key，且必须对搜索结果再做域名、原文与状态核验。以下为 2026-10-05 查看官方公开价格后的备选，**未注册、未购买、未接入**：

| 方案 | 公开额度与价格 | 适用性与限制 |
| --- | --- | --- |
| [Tavily Search](https://www.tavily.com/pricing) | 每月 1,000 API credits 免费、无需信用卡；按量 $0.008/credit，复杂搜索可能消耗多 credit | 便于低成本验证；中国校园/比赛网络连通与中文官网召回尚未实测 |
| [Brave Search API](https://brave.com/search/api/) | Search $5/千次，每月 $5 credit（相当于约 1,000 次）；注册仍需信用卡验证 | 独立索引；中国网络连通未实测，注册门槛较高 |
| [阿里云 OpenSearch 联网搜索](https://help.aliyun.com/zh/open-search/search-platform/product-overview/web-search-billing-change-announcement) | Lite 12 元/千次，Pro 36 元/千次，Max 46 元/千次；未在公开页确认免费额度 | 国内服务候选；需账号、Key 和收费开通，国内赛事网络稳定性仍需现场测试 |
| [腾讯云联网搜索 API](https://cloud.tencent.com/document/product/1806/121798) | 轻量 18 元/千次，标准 46 元/千次；未在公开页确认免费额度 | 国内服务候选；需账号与计费，[个人实名认证用户](https://cloud.tencent.com/document/product/1806/121799)可开通轻量版或标准版后付费；校园网络需实测 |

推荐先维持本轮登记官网读取；若确需开放发现，优先以 Tavily 免费额度做受控样本测试，并验证中国校园网络与官方来源命中率。若境外服务不稳定，再经费用审批比较国内服务。Google Custom Search JSON API 已[关闭新用户](https://developers.google.com/custom-search/v1/overview)，不作为新接入候选。

旧 [AI V1 文档](ai-chat.md) 保留最初实现背景；以本文为当前 V2 行为依据。
