# AI 问答优化交付说明

本次交付改进站内多轮理解、证据筛选、流式交互，并提供可选 SearXNG 联网搜索。没有新增数据库表、迁移或项目依赖。以下清单是本轮交付范围，共 28 个文件；不包含原有资源分类改动。

## 功能与行为

- 多轮由现有模型先生成独立检索问题，识别追问、条件变化和换题。程序校验签名对象及序号；比较原推荐时固定列表顺序，重新读取公开资料；无结果或澄清不清空原列表，明确换题后切换主题。
- 人数、学历、学校等条件参与本轮理解。缺少资格或人数依据时说明待确认，不把准备建议当成已满足参赛条件。科研介绍、成果和招募分别取证。
- 检索筛除重复与无关候选，来源预算优先覆盖不同对象，推荐必须对应本轮证据。结束时校验引用编号和链接；生成中及未完成回答不开放正文链接。
- “联网搜索”位于发送键左侧，仅显示按钮文字，默认关闭；关闭时后端禁止所有站外调用，开启后可读取站外正文并展示来源。搜索摘要本身不作为证据。
- 停止立即冻结输出并允许继续操作；重试不重复提问，旧请求不能覆盖新请求，未完成回答不进入成功历史。

## 提交文件清单

### 后端：15 个

```text
backend/.env.example
backend/ai_services/chat.py
backend/ai_services/conversation.py
backend/ai_services/evidence.py
backend/ai_services/external_search.py
backend/ai_services/fusion.py
backend/ai_services/test_chat.py
backend/ai_services/test_conversation.py
backend/ai_services/test_external_search.py
backend/ai_services/test_stream_chat.py
backend/ai_services/unified.py
backend/ai_services/views.py
backend/ai_services/web.py
backend/config/settings.py
backend/ingestion/http.py
```

包含会话理解、检索与生成、引用校验、外部正文读取、请求契约及正式回归测试。网页读取沿用公网地址校验、固定 IP 连接、重定向限制和 robots 检查，增加共享读取时间预算。

### 前端：9 个

```text
frontend/src/api/ai.js
frontend/src/api/aiResponse.js
frontend/src/api/aiStream.js
frontend/src/components/AICompetitionAssistant.vue
frontend/src/composables/useAIChat.js
frontend/src/utils/aiMarkdown.js
frontend/tests/aiChat.test.js
frontend/tests/aiMarkdown.test.js
frontend/tests/aiStream.test.js
```

包含联网开关、签名上下文透传、流式状态管理、安全链接渲染，以及停止、迟到响应和重试的正式回归测试。

### 启动与配置：3 个

```text
deploy/searxng/settings.yml
scripts/start-searxng.ps1
scripts/dev.ps1
```

前两项提供本机搜索服务配置与启动；`dev.ps1` 修复可执行文件存在多个候选路径时的启动错误。

### 唯一交付文档：1 个

```text
docs/ai-optimization-20261008.md
```

正式回归测试属于工程文件，随功能一并提交。人工评测题集、手工验证脚本、输出、截图和日志留在已被 Git 忽略的 `.local/`，不在上述清单内。真实 `.env`、密钥、数据库、模型、索引、Docker 运行数据和构建产物均不提交。

以下是原工作区已有的另一组资源分类改动，本轮保留但不纳入提交范围：

```text
backend/curation/activation.py
backend/curation/test_activation.py
backend/curation/resource_classifications.py
docs/competition-search-handoff.md
docs/competition-knowledge-maintenance/imports/resource-classifications.json
scripts/build-resource-classifications.py
```

`docs/progress.md`、`docs/ai-v3.md` 的本轮新增说明已撤下，本次只交付本文件。提交时按上述清单选择文件，不直接暂存整个工作区。

## 配置与启动

继续使用已有 Django、数据库、模型 API 和检索索引配置；本次不需要数据库迁移。多轮理解复用聊天模型，不需要新增模型密钥。多进程部署应使用同一个 Django `SECRET_KEY`，以验证会话签名。

### Windows 本机搜索

1. 安装并启动 Docker Desktop，使用 Linux containers，等待引擎就绪。
2. 项目根目录执行 `./scripts/start-searxng.ps1`。脚本创建 `chuangxiang-search`，生成随机服务密钥，将配置只读挂载到容器，仅监听 `127.0.0.1:8888`，开启 JSON 搜索。
3. 在不入库的 `backend/.env` 设置：

   ```dotenv
   AI_SEARXNG_URL=http://127.0.0.1:8888
   ```

4. 重启后端，在助手中开启“联网搜索”后验证回答来源。

搜索根地址不包含 `/search`。检查服务：

```powershell
(Invoke-RestMethod 'http://127.0.0.1:8888/search?q=Python&format=json').results |
    Select-Object -First 3 title,url
```

停止与恢复：`docker stop chuangxiang-search`、`docker start chuangxiang-search`。容器配置为 `unless-stopped`；电脑重启后需要 Docker 引擎运行。留空 `AI_SEARXNG_URL` 并重启后端，可关闭通用搜索；原登记官网适配器仍存在，但前端关闭联网时同样不会调用。

本机已实际运行并验证。镜像、JSON 接口说明见 [SearXNG 官方安装文档](https://docs.searxng.org/admin/installation-docker.html)和[搜索 API](https://docs.searxng.org/dev/search_api.html)。

### 队长或服务器部署

上述工程配置可迁移，真实模型配置与数据库按原项目方式准备。Windows 可使用同一启动脚本；Linux 服务器需自行在现有 Docker Compose 中加入 SearXNG，挂载本次配置并生成独立服务密钥。

后端也在容器中时，应将 `AI_SEARXNG_URL` 设为同网络可达的服务地址，例如服务名为 `searxng` 时使用 `http://searxng:8080`；不能照搬本机 `127.0.0.1:8888`。无需将搜索端口向公网开放。本次没有修改生产 Compose，也没有完成目标服务器部署验收。

## 接口与运行边界

聊天请求保留 `messages`、`mode`，新增可选字段：

- `conversation_context`：上一成功回答返回的服务器签名字符串，前端原样透传；签名有效期 24 小时且绑定模式，不用历史回答恢复事实。
- `web_search`：严格布尔值。`false` 禁止站外调用，`true` 为非闲聊问题请求外部补充；省略时兼容原自动策略。新前端默认发送 `false`。

流式事件为 `status`（`retrieving` / `generating`）、`delta`、`done` 或 `error`。最终来源、推荐和上下文只在 `done` 接受；输入和配置错误仍在流开始前返回 JSON 错误。旧客户端可忽略 `status`。

多轮理解读取最近 6 轮（历史每条最多 1200 字）、完整当前问题和签名状态，输出上限 768 token，请求超时配置不超过 12 秒，不自动重试。无效输出回退规则。这增加一次模型调用及一定延迟；不是独立训练的新模型。

通用网页搜索默认最多读取 3 页、15 秒共享预算，成功结果缓存 5 分钟，保留原读取时间。读取时间不等于发布日期。明确配置的官方域名可获官方来源标签，其余为 Web 补充；站外页面均不冒充人工核验。

## 验证结果

以下为交付前实际验证结果；不以固定题集通过率代替总体准确率。

| 验证 | 命令或范围 | 结果 |
| --- | --- | --- |
| 后端相关回归 | 在 `backend` 执行 `.venv\Scripts\python.exe manage.py test ai_services ingestion.tests.AdapterTests config --settings=config.test_settings --noinput` | 213 项通过 |
| Django 检查 | 在 `backend` 执行 `.venv\Scripts\python.exe manage.py check` | 无问题 |
| 前端回归 | 在 `frontend` 执行 `npm test` | 70 项通过 |
| 前端构建 | 在 `frontend` 执行 `npm run build` | 通过 |
| 真实模型验收 | 19 轮：原话、改写、条件变化、换题、方向细化、歧义和网页阅读 | 19/19 断言通过，并人工抽查 |
| 实际页面验收 | 三轮“机器人推荐 → 三人选哪个 → 第三个介绍”；另验证联网开关 | 历史透传、原列表顺序、RoboMaster 指代和开关行为通过 |
| 流式交互 | 停止、部分错误、重试、迟到响应、手机布局 | 通过 |
| 静态检查 | PowerShell 语法、`git diff --check` | 通过 |

仍需留意：模型理解和自然语言论断存在误判可能；引用编号正确不等于每句话均有充分依据。上游搜索引擎可能限流，部分页面无法读取；一次尚未返回的 DNS/网络操作可能延后预算退出。实际部署对断连和模型停止计费的响应受 WSGI、代理与模型服务影响。完整采集互斥测试需要 PostgreSQL，本机账号无创建测试库权限，因此未宣称全仓库测试通过。
