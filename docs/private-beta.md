# Windows 邀请内测

本版基于主分支 `65e7af2`，在独立工作树 `Chuangxiang-Community-beta-ai` 运行新的赛事助手。内测数据库为 `chuangxiang_beta_20261006_ai`；旧内测数据库与旧工作树保留。通用功能交接见 [赛事助手交接](ai-assistant-handoff.md)。

本轮提供 10 个普通测试账号和 2 个管理员账号，原有账号密码保留。账号清单、入口口令和个人邀请文件仅保存在本机 `.local/private-beta/chuangxiang_beta_20261006_ai/`，不提交 Git。入口口令与站内账号登录分别使用；管理员密码不发给普通测试者。

入口验证成功后，浏览器保存 4 小时有效的签名入口 Cookie，让页面、资源和 API 请求使用同一入口验证状态。更换入口口令或域名后失效；站内账号仍需正常登录，组队等操作继续检查用户权限。

## 本机配置

`backend/.env` 仅保存本机的三项 DeepSeek 配置，真实 Key 由负责人填写：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

无须开启旧内部草稿服务的 `AI_ENABLED`。密钥不写入前端、邀请文件或日志。代码默认超时为 60 秒、输出上限为 2048 tokens；赛事回答另设较小的生成预算。

内测专用 `.env` 位于 `.local/private-beta/chuangxiang_beta_20261006_ai/.env`，保存独立数据库连接、Django 密钥、入口口令和私有目录。首次配置可复制 [配置样例](../deploy/private-beta/.env.example)，填写本机绝对路径与凭据，不能覆盖负责人已有的 `.env`。数据库须事先建立并授予本机数据库用户访问权限。以下为本轮数据库及检索配置：

```dotenv
PRIVATE_BETA_DB_NAME=chuangxiang_beta_20261006_ai
COMPETITION_EMBEDDING_MODEL_PATH=本机工作树/.local/models/bge-small-zh-v1.5
COMPETITION_SEMANTIC_INDEX=本机工作树/.local/competition-search/database.npz
PUBLIC_RESEARCH_ENABLED=0
```

这里的路径文字需替换为实际绝对路径。`PRIVATE_BETA_FRONTEND_DIST` 指向私有运行目录下的 `frontend-dist`；`PRIVATE_BETA_STATE_DIR` 指向该私有运行目录。内测配置优先加载该文件，再加载 `backend/.env`；不要在两个文件重复保存不同的 DeepSeek 配置。

`PRIVATE_BETA_ORIGIN` 由启动器更新为本次精确 HTTPS 隧道域名，允许主机和 CSRF 来源均使用该域名。邮件写入私有目录的 `mail/`，本版不发送真实邮件；测试者采用已准备的账号。

## 准备顺序

在新工作树根目录执行，使用 Python 3.13 虚拟环境。内测数据库、账号及专用 `.env` 须先由负责人准备好。

1. **安装依赖、准备前端。** 基础依赖、Waitress 和 BGE 检索依赖安装到同一环境。

   ```powershell
   $betaPython = Join-Path $PWD 'backend/.venv/Scripts/python.exe'
   $betaRuntime = Join-Path $PWD '.local/private-beta/chuangxiang_beta_20261006_ai'
   & $betaPython -m pip install -r backend/requirements-private-beta.txt
   & $betaPython -m pip install -r backend/requirements-retrieval.txt
   npm.cmd --prefix frontend ci
   $env:VITE_PRIVATE_BETA = '1'
   npm.cmd --prefix frontend run build -- --outDir "$betaRuntime/frontend-dist"
   Remove-Item Env:VITE_PRIVATE_BETA
   ```

2. **准备本地模型。** 执行 `scripts/prepare-competition-model.py` 下载 `BAAI/bge-small-zh-v1.5`，固定 revision 为 `7999e1d3359715c523056ef9478215996d62a620`。模型下载与 DeepSeek 调用无关；查询时仅从本地加载。

   ```powershell
   & $betaPython scripts/prepare-competition-model.py
   $env:COMPETITION_EMBEDDING_MODEL_PATH = Join-Path $PWD '.local/models/bge-small-zh-v1.5'
   $env:COMPETITION_SEMANTIC_INDEX = Join-Path $PWD '.local/competition-search/database.npz'
   ```

   同样的两个绝对路径须保存到 `backend/.env`，供服务重启后使用。本机通过官方固定 revision 下载的模型已核验；记录在 `.local/models/bge-small-zh-v1.5-download-verification.json`。

3. **迁移、准备账号并导入当前资料。** 以下命令显式使用内测设置，连接新内测库。账号命令按目标总数补充学生账号，已存在的账号、密码及队伍关系保留。创建的邮箱仅为内测标识，验证码流程使用本地文件邮件。

   ```powershell
   $env:PRIVATE_BETA_ENV_FILE = Join-Path $betaRuntime '.env'
   & $betaPython backend/manage.py migrate --settings=config.private_beta_settings
   & $betaPython backend/manage.py prepare_private_beta --students 10 --markdown --settings=config.private_beta_settings
   $actorId = [int](Read-Host '新内测库中的管理员用户 ID')
   & $betaPython backend/manage.py load_competition_knowledge --actor-id $actorId --apply --reason '启用赛事助手内测资料' --settings=config.private_beta_settings
   ```

   管理员用户 ID 可在本机生成的 `accounts.json` 中查看。账号总表为 `内测账号清单-仅负责人.md`，个人邀请为 `invitations/内测邀请-01.md` 等文件。`--students` 表示学生账号总数（1—50），不是每次新增的数量；默认 5。再次执行会保留已有账号，人数调小也不删除账号。仅导出当前账号材料时，使用同一命令即可。

4. **重建当前数据库的 BGE 索引。** 模型路径与语料准备好后再执行；以后每次更新资料均须重新建索引。

   ```powershell
   & $betaPython backend/manage.py rebuild_ai_index --settings=config.private_beta_settings
   ```

   索引应来自当前内测数据库，不能复用离线 `corpus.json` 的评测索引。查询遇到缺失或过期索引会退回关键词检索；验收需检查 `mode_used=hybrid`，并在底层检索结果中确认 `warnings` 为空。

## 启停与邀请

负责人核对已有 8010、8011 服务的归属后再切换到新工作树；脚本遇到端口占用会拒绝启动，不会关闭其他服务。Cloudflare 可执行文件放在 `.local/tools/cloudflared.exe`。

```powershell
./scripts/private-beta.ps1 -Action start -PythonPath $betaPython
./scripts/private-beta-admin.ps1 -Action start -PythonPath $betaPython
```

两种服务都在 Windows 后台隐藏运行。主服务监听 `127.0.0.1:8010`，Cloudflare 临时隧道将其提供给受邀测试者；管理员服务监听 `127.0.0.1:8011`，仅在本机访问 `http://127.0.0.1:8011/admin/`，不加入公网隧道。

主启动器保存进程、日志和已验证的 Python 路径；停止只针对本次记录的进程及其已核对的 Python 子进程。重启可能更换公网域名，成功启动后会更新账号总表、编号 01—50 范围内已有的个人邀请（`.md`、`.txt`）和负责人使用说明中的地址。检查认证与页面后，分别发给对应测试者，不分享整个私有目录。

```powershell
./scripts/private-beta.ps1 -Action status
./scripts/private-beta-admin.ps1 -Action status
./scripts/private-beta-admin.ps1 -Action stop
./scripts/private-beta.ps1 -Action stop
```

电脑需保持开机、联网及 PostgreSQL 运行。电脑休眠或服务停止后，先恢复 PostgreSQL，再按上述命令启动内测服务。后端启动前最多等待数据库 120 秒，两种启动器最多等待后端 180 秒；`status` 显示运行仅代表进程存在，仍需打开网页验证。数据库异常退出后的自动恢复可能超过数据库启动脚本等待时间，应查看数据库状态，不能重新初始化数据目录。公开服务运行时，每分钟在新内测数据库执行组队截止结算；本机管理员进程不重复运行该维护任务。

## 验收记录

2026-10-06 在本工作树执行的无模型检查：

- `scripts/check-competition-knowledge.py` 通过：资料版本 `d744beaf5c993b25`，255 项目录、198 篇正文、912 段，20 项样本，无错误。
- `scripts/check-knowledge-rebuild.py` 通过：使用本地快照在 `.local/knowledge-rebuild-*` 重建，11 份公开产物逐字节一致。没有联网或写数据库。
- `backend/manage.py makemigrations --check --dry-run --settings=config.test_settings` 通过：`No changes detected`。
- BGE 上游 11 个文件共 96,405,966 字节；权重通过官方 LFS SHA-256 校验，其余文件通过 Git blob 哈希校验。

实际公网验收已完成：自然语言搜索得到 5 个候选，`understanding=model`、`mode_used=hybrid`；推荐、分析和找队友三个阶段均为 `answer.mode=model`。分析结果关联 4 项学习资源，05 号账号发布的测试招募被 04 号账号命中，随后完成申请、接受和双方确认入队。未变化的会话刷新复用原回答。证据保存在私有运行目录的 `ai-guide-verification.json` 及三个响应 JSON 中。

本地索引包含 912 段，底层检索 `warnings=[]`。公开接口验证资源 302 项、知识文档 500 项（198 篇赛事正文加 302 篇学习资源说明）、科研 0 项。原 7 个账号及旧队伍关系保留，旧资料归档不删除。后端专项 61 项、内测隔离与维护 28 项、账号准备 7 项，以及前端 58 项测试通过。

普通有候选的“输入需求 → 点击分析 → 点击找队友”约调用 DeepSeek 4 次；刷新恢复不调用模型。固定题集的 Hit@5 是检索指标，不等于完整回答准确率。本轮未运行整套付费模型评测。

发布前追加验证：内测入口与数据库启动检查 39 项、账号扩容与私有 Markdown 导出 14 项通过。Windows 两种启动器通过语法及共 10 项进程身份检查。实际新增学生 06—10，保留全部原账号凭据，生成 1 份负责人总表与 10 份个人邀请。`scripts/retire-private-beta-snapshot.py` 仅用于本轮旧资料副本的一次性归档，不属于新环境常规初始化步骤。
