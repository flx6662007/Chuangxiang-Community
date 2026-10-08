# AI 助手第一阶段：DeepSeek 基础聊天（历史记录）

当前 V2 行为与操作请读 [多源可信检索开发说明](../ai-v2.md)。以下内容记录第一阶段实现时的状态，其中“尚未接入检索”等描述不再代表当前代码。

2026-10-04：首页 AI 助手已从模拟赛事搜索改为真实模型聊天调用。代码和离线验证已完成；本机尚未配置 DeepSeek Key，因此真实模型回复、账号余额和线上延迟尚未验证。

## 项目与调用链

现有前端是 Vue 3 / JavaScript / Vite，使用 Vue Router、Axios、Element Plus。首页 `WelcomeView.vue` 挂载 `AICompetitionAssistant.vue`，原先调用 `services/aiCompetitionSearch.js` 和 `mocks/aiCompetitionSearch.js`，展示虚构赛事。旧模拟模块及测试保留，但首页不再调用。

后端继续使用 Django / DRF / PostgreSQL，账号为 Session + CSRF。已有 `ai_services` 的兼容客户端原先用于通知字段提取和快讯草稿，没有聊天接口。本次复用 HTTPX、配置校验及异常类别，未增加依赖、数据库表或迁移。既有内部草稿功能仍使用原来的 `AI_SERVICES` / `AI_ENABLED` 配置。

```text
AICompetitionAssistant.vue / useAIChat.js
  → src/api/ai.js → 统一 Axios src/api/http.js（CSRF、Vite /api 代理）
  → POST /api/v1/ai/chat/
  → ai_services/views.py（格式、CSRF、限流、固定错误文案）
  → ai_services/chat.py（历史消息校验、服务器 System Prompt）
  → OpenAICompatibleClient.complete_text()
  → https://api.deepseek.com/chat/completions
```

业务层依赖 `complete_text(messages)`，可以注入其他客户端；模型名和基础地址由服务器配置。本次没有接入站内数据、RAG、联网搜索、工具调用、Agent、用户画像或长期记忆。

## 本机配置

在编辑器中打开项目内的 **`backend/.env`**，保留现有数据库和 Django 配置，在末尾添加以下变量。**只在本机文件中把真实 Key 粘贴到 `DEEPSEEK_API_KEY=` 后面，不发到聊天，不写到前端。**

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_TIMEOUT_SECONDS=60
DEEPSEEK_MAX_OUTPUT_TOKENS=2048
```

填写后重启 Django。进程环境变量优先于 `.env`。不必把 `AI_ENABLED=0` 改成 `1`；它控制原有内部草稿服务，首页聊天独立使用 `AI_CHAT`。没有 Key 时服务器正常启动，聊天返回安全的 503 配置提示。

采用当前官方文档列出的 **`deepseek-flash`**，基础地址 **`https://api.deepseek.com`**。请求为 OpenAI-compatible Chat Completions、`stream: false`、`thinking: {"type": "disabled"}`。仅返回最终文本，不返回推理内容、授权信息或上游原始对象。

超时参数为 HTTPX 各网络阶段的超时（1–120 秒），不是严格的总执行时长；前端单次等待上限 130 秒。默认输出上限为 2048 tokens，可配置范围 1–8192。服务不自动重试；被截断、为空、超长或格式错误的回答显示友好提示，用户自行重试。前端取消会停止等待，但已经送往模型的请求可能仍被处理和计费。

配置样例可共享；实际 `.env` 被根目录 `.gitignore` 忽略。这一阶段验证的是本机启动方式，未修改或验证 Docker 部署配置。

## 启动和操作

沿用已配置的 Python 虚拟环境和 PostgreSQL，在项目根目录打开两个终端：

```bash
# 终端一
cd backend
./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

```bash
# 终端二
cd frontend
npm run dev
```

打开 <http://localhost:5173/#ai>，保持前后端运行。本次没有新依赖或迁移。新电脑的首次安装和数据库初始化仍见 [后端开发](../backend-development.md) 和 [前端说明](../../frontend/README.md)。界面预览脚本不会启动后端，不能单独用于验证真实 AI。

依次发送：

1. “你好，你是谁？”
2. “你主要能帮我做什么？”
3. “我刚才第一个问题问了什么？”

第三条应能引用第一条。Enter 发送，Shift + Enter 换行，中文输入法确认候选不会发送。等待时禁用重复提交；失败问题保留并可重试，也可以改问。新消息自动滚动，对话以转义后的纯文本显示，保留换行，不执行 HTML。

当前页面内存保存聊天；刷新或离开首页后清空。每次最多发送最近 20 轮完整对话及本次问题，总计最多 60000 字符。单条用户消息最多 2000 字符，助手回复最多 16000 字符。达到上下文窗口限制时舍弃最早的完整轮次，当前页显示记录仍保留。失败提示不进入模型上下文。

## 接口契约

游客和登录用户均可使用首页聊天。POST 必须有 CSRF Cookie/请求头，前端复用 `/api/v1/accounts/csrf/`。接口按 IP 做每分钟 10 次基础限流，超限 429；这不是完整计费配额系统。上线前需按实际代理和用户规模另行验证限流及预算。

请求：

```json
{"messages":[{"role":"user","content":"你好"}]}
```

响应：

```json
{"message":{"role":"assistant","content":"你好，我是创享平台的高校科创 AI 助手。"}}
```

只接受交替的 `user` / `assistant`，以 `user` 开始和结束。前端不能提交 `system`、模型配置、工具或其他额外字段。System Prompt 在 `backend/ai_services/chat.py` 管理，明确当前没有实时数据库及联网能力。用户的文字仍是用户输入，不能通过接口字段替换服务器提示词。

错误统一为 `{ "code": "...", "detail": "适合展示的中文提示" }`。非法输入 400；CSRF 失败 403；限流 429；上游故障/无效回复 502；缺配置、认证失败、余额不足、连接失败 503；超时 504。浏览器不接收上游原始错误，响应设置 `Cache-Control: no-store`。

## 验证

```bash
cd backend
./.venv/bin/python manage.py check
./.venv/bin/python manage.py test ai_services config --settings=config.test_settings
```

```bash
cd frontend
npm test
npm run build
```

后端测试使用 MockTransport；测试标记令牌只存在于测试内存中，不写入 `.env`，不发送到 DeepSeek。覆盖三轮调用契约、固定提示词、缺配置、认证/余额/限流/超时/网络/异常响应、CSRF、输入边界、日志与响应脱敏。前端测试覆盖多轮、重复提交、失败重试、上下文窗口、卸载取消和安全错误展示。

真实 Key 未填写前，这些检查不能证明官方 API 已成功调用。填好后按上述三条问题完成人工联调，并在浏览器 Network 中确认只请求本站 `/api/v1/ai/chat/`，请求仅包含历史消息、响应仅包含助手文本或安全错误。

## 官方依据（2026-10-04 核对）

- [首次调用 API：基础地址与当前模型名](https://api-docs.deepseek.com/zh-cn/)
- [Chat Completions：消息和 thinking 参数](https://api-docs.deepseek.com/api/create-chat-completion/)
- [错误码：401、402、429、500、503](https://api-docs.deepseek.com/zh-cn/quick_start/error_codes/)
