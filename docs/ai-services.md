# AI 服务

`backend/ai_services/` 集中管理模型调用、提示词、结果校验和异常。它是后端内部服务包，不是 Django 应用，不创建数据库表或 HTTP 接口，也不自动采集、入库或发布。当前已具备基础代码与离线测试；真实模型连接、效果和费用尚未验证。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `config.py` | 读取并检查服务端模型配置 |
| `client.py` | 通过 HTTPX 调用兼容 Chat Completions 的服务，要求 JSON 输出 |
| `prompts.py` | 通知提取、快讯生成两类提示词 |
| `validators.py` | 检查字段、引文、缺失值和来源映射 |
| `exceptions.py` | 定义配置、输入、网络、上游响应和校验异常 |
| `services.py` | 组合提示词、调用和校验，提供业务入口 |
| `test_*.py` | 使用模拟响应进行离线测试 |

## 配置

参数写在本机 `backend/.env`，由 Django 的 `settings.AI_SERVICES` 读取。配置样例见 [`backend/.env.example`](../backend/.env.example)。不修改队友的本地配置，不提交真实密钥。

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `AI_ENABLED` | `0` | 设为 `1` 后才允许真实模型调用 |
| `AI_PROVIDER` | `qwen` | 支持 `qwen`、`openai_compatible`；Qwen 请求关闭思考模式 |
| `AI_BASE_URL` | 空 | HTTPS 兼容接口基础地址，按服务控制台填写 |
| `AI_API_KEY` | 空 | 服务端密钥，须与服务区域和地址匹配 |
| `AI_MODEL` | 空 | 控制台支持的模型名，当前没有确定最终模型 |
| `AI_TIMEOUT_SECONDS` | `30` | HTTPX 请求各阶段的超时设置，并非任务总时长上限 |
| `AI_MAX_OUTPUT_TOKENS` | `2048` | 单次生成的输出 token 上限 |

Qwen 是候选提供方，兼容协议也允许后续替换服务。不同提供方对 JSON 模式和参数的支持需要实际验证。地址与授权以对应服务控制台及官方文档为准。

## 调用入口

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

服务不自动重试，避免失败后未经判断重复调用产生费用；`retryable` 是可重试提示，不表示已重试。异常不包含密钥或上游原始响应。后续日志也不要直接记录完整密钥、学生资料或原始模型响应。

在 `backend/` 目录运行离线测试：

```powershell
.\.venv\Scripts\python.exe manage.py test config ai_services
```

这些测试不需要模型密钥、不访问真实模型服务；通过后仍需进行真实 API 联调和人工标注样本评测，才能确定模型与发布流程。

## 官方参考

- [阿里云：OpenAI 兼容接口](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)
- [阿里云：结构化输出](https://help.aliyun.com/zh/model-studio/qwen-structured-output)
- [HTTPX：超时配置](https://www.python-httpx.org/advanced/timeouts/)
