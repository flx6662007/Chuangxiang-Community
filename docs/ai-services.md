# AI 服务

`backend/ai_services/` 管理首页聊天、赛事向导、检索、模型调用和结果校验；另保留通知提取及快讯草稿服务。模块本身不定义业务表，检索读取现有公开数据，向导状态使用 Django Session；模型输出不会自动入库、发布或替用户申请。

本页按 2026-10-08 代码区分两套配置。当前接入见[AI 助手说明](ai-v3.md)，近期功能与历史联调见[科研交付](releases/research-ai-20261007.md)和[多轮与联网交付](ai-optimization-20261008.md)。历史真实调用已记录，目标环境的密钥、余额、网络与部署仍须单独验收。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `config.py` | 读取并检查服务端模型配置 |
| `client.py` | 通过 HTTPX 调用兼容 Chat Completions 服务，支持文本、SSE 流式和 JSON 输出 |
| `urls.py`、`views.py` | 公开聊天、流式、关键词搜索、配置状态；处理 CSRF、限流及安全错误响应 |
| `chat.py`、`conversation.py` | 对话处理、多轮理解、签名上下文、检索和生成流程 |
| `unified.py`、`competition_knowledge.py`、`unified_index.py` | 公开资料检索、赛事正文适配及资源/科研 BGE 索引 |
| `research_retrieval.py`、`evidence.py`、`fusion.py` | 科研条件筛选、证据组织、引用与链接校验 |
| `web.py`、`external_search.py` | 登记官网与可选 SearXNG 搜索、正文读取及来源标记 |
| `guide_views.py`、`guide.py`、`guide_answer.py` | 赛事向导 Session、条件匹配、招募查询及回答 |
| `prompts.py`、`validators.py`、`services.py` | 原内部通知提取/快讯草稿的提示词、校验与调用入口 |
| `exceptions.py` | 定义配置、输入、网络、上游响应和校验异常 |
| `test_*.py` | 使用模拟响应进行离线测试 |

## 首页聊天与赛事向导配置

配置仅写入目标环境的服务端 `backend/.env`，样例见 [`backend/.env.example`](../backend/.env.example)。首页聊天和向导读取 `settings.AI_CHAT`，与 `AI_ENABLED` 无关：

| 参数 | 默认值或要求 |
| --- | --- |
| `DEEPSEEK_API_KEY` | 无默认密钥；必须配置有效服务端密钥 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com`，实际地址须通过配置校验 |
| `DEEPSEEK_MODEL` | `deepseek-flash`，目标账号须可调用该模型 |
| `DEEPSEEK_TIMEOUT_SECONDS` | `60`，HTTPX 请求阶段超时，不等于完整任务总时长 |
| `DEEPSEEK_MAX_OUTPUT_TOKENS` | `2048`，生成输出上限 |
| `DEEPSEEK_PROXY_URL` | 可选显式本机 HTTP 代理；无需代理时留空 |
| `PUBLIC_RESEARCH_ENABLED` | 默认 `0`；设为 `1` 才开放科研公共读取及 AI 资料 |
| `AI_SEARXNG_URL` | 可选搜索服务根地址，留空时不启用通用 SearXNG 搜索 |

`AI_CHAT.ENABLED` 在设置中为真，但仍须有效模型配置。配置状态接口只检查格式；真实调用可能因鉴权、余额、网络等失败。模型和索引配置、两种聊天接口、联网开关及会话约定见[AI 接入](ai-v3.md)。普通卡片浏览不调用模型，用户发送问题后才进入 AI 流程。通用聊天多轮理解与回答生成可能分别调用模型，不能按一次发送必定一次模型请求估算费用。

密钥不发送给前端、不提交 Git。更新配置后需重启对应服务；拉取代码不会自动导入资料、生成索引或改变正在运行的实例。

## 内部草稿配置

以下参数仅用于 `settings.AI_SERVICES` 的通知提取和快讯草稿；它们默认关闭，不会随首页聊天启用。

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `AI_ENABLED` | `0` | 设为 `1` 后才允许内部草稿服务调用模型 |
| `AI_PROVIDER` | `qwen` | 支持 `qwen`、`deepseek`、`openai_compatible`；Qwen / DeepSeek 请求关闭思考模式 |
| `AI_BASE_URL` | 空 | HTTPS 兼容接口基础地址，按服务控制台填写 |
| `AI_API_KEY` | 空 | 服务端密钥，须与服务区域和地址匹配 |
| `AI_MODEL` | 空 | 内部草稿使用的模型名，需单独配置 |
| `AI_TIMEOUT_SECONDS` | `30` | HTTPX 请求各阶段的超时设置，并非任务总时长上限 |
| `AI_MAX_OUTPUT_TOKENS` | `2048` | 单次生成的输出 token 上限 |

Qwen 是候选提供方，兼容协议也允许后续替换服务。不同提供方对 JSON 模式和参数的支持需要实际验证。地址与授权以对应服务控制台及官方文档为准。

## 内部草稿调用入口

在 Django 已加载配置的环境中调用，例如后续管理任务或 `manage.py shell`：

```python
from ai_services import extract_notice, generate_newsletter

notice = extract_notice(source_text, source_url)
draft = generate_newsletter(items)
```

两个函数均可通过 `client=` 注入测试客户端。当前为同步函数，后续可交由后台任务执行；浏览赛事卡片时读取已保存数据，不调用模型。

**通知提取：**输入通知原文及其来源 URL；原文最多 20,000 字符。返回 `source_url`、`fields`、`missing_fields`、`requires_review`。`fields` 包含 `title`、`organizer`、`eligibility`、`registration_deadline`、`submission_deadline`，每项均为 `{"value": ..., "evidence": ...}`。

- 普通文本值须能在对应引文中找到，引文须逐字出现在原文中。
- 日期仅接受有明确年月日依据的日期，支持连字符、斜杠或中文年月日形式；不猜年份，也不补时间。
- 缺失字段必须为 `{"value": null, "evidence": null}`，并计入 `missing_fields`。

**快讯生成：**输入最多 10 条 `{"id", "title", "source_url", "content"}`，由调用方先筛选已经核实且仍有效的资讯；标题与正文总计最多 20,000 字符。返回 `title`、`items`、`requires_review`；每条结果包含 `source_id`、`title`、`source_url`、`summary`、`evidence`。来源 ID 必须引用输入，单条标题及 URL 由后端从输入回填，引文须出现在对应正文中。

超长输入直接报错，不静默截断。两类结果均标记 `requires_review=true`。校验只能检查格式、引文和引用关系，不能保证来源权威、资讯仍然有效或摘要语义完全准确；管理员仍需确认。

## 异常与测试

调用方可统一捕获 `ai_services.exceptions.AIServiceError`，根据其 `.code` 和 `.retryable` 决定如何向管理员提示或安排后续处理。细分类别包含配置错误、输入错误、超时、连接失败、鉴权失败、限流、上游错误、响应格式错误和结果校验错误。

内部草稿服务不自动重试；`retryable` 是可重试提示，不表示已重试。异常不包含密钥或上游原始响应。不要在日志记录完整密钥、学生资料或原始模型响应。聊天与向导另有面向用户的错误和规则降级处理；请求失败不代表已生成可发布内容。

在 `backend/` 目录运行离线测试：

```powershell
.\.venv\Scripts\python.exe manage.py test config ai_services --settings=config.test_settings --noinput
```

这些测试使用模拟客户端与独立测试设置，不需要真实模型密钥，也不能证明上游服务可用。当前已有相关离线回归和历史真实模型联调记录，详见本页开头的交付说明；新环境仍应核验资料发布范围、配置、真实回答来源和流式交互。固定题集的检索命中率不能换算为完整问答准确率，内部草稿通过格式校验也仍须人工审阅。

## 官方参考

- [阿里云：OpenAI 兼容接口](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)
- [阿里云：结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output)
- [HTTPX：超时配置](https://www.python-httpx.org/advanced/timeouts/)
