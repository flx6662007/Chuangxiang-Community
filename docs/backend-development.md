# 后端开发

## 当前范围

已接入 Django/DRF、PostgreSQL、公开赛事 API、赛事管理后台、学校邮箱账号和本人资料；前端已接入列表、详情及账号页面。本轮先交付无需购买服务的本地开发版，邮件输出到终端，AI 默认关闭。没有真实赛事采集、真实邮件投递或公网部署。

完整状态见 [团队进度](progress.md)，接口见 [API 说明](api.md)，页面操作见 [人工验收](manual-checks.md)。[数据库交付说明](database-handoff.md) 保留同学交付时的模型、迁移、约束和样例记录；其中“接口待实现”等历史状态由本轮进度替代，字段规则不因此改变。

## 首次配置

### 获取代码

新电脑准备 Python 3.13、PostgreSQL 17、Git；启动前端还需要符合 `frontend/package.json` 要求的 Node.js 与 npm。

```powershell
git clone https://github.com/flx6662007/Chuangxiang-Community.git
Set-Location .\Chuangxiang-Community
git branch --show-current
git status
```

默认克隆 `main`，本轮赛事与账号成果已通过 PR #3 合入主分支。已有仓库先提交或妥善保存自己的改动，再获取最新主分支，避免覆盖未提交工作。后续从最新主分支新建自己的任务分支，提交状态见 [团队进度](progress.md)。

### 安装依赖

从仓库根目录进入一次 `backend`，后续后端命令均在这里执行。目录中应有 `manage.py`：

```powershell
Set-Location .\backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

已有虚拟环境无需重建；依赖变更后重新执行安装命令。已有 `.env` 不要覆盖，对照样例补新增项。若不识别 `py`，用已安装 Python 3.13 的完整路径代替。直接调用虚拟环境 Python，无需运行激活脚本。

Linux 对应命令：

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
```

### 数据库与配置

在 PostgreSQL 中建立自己的空开发数据库与普通登录用户，让该用户拥有此数据库；例如库名、用户名都用 `chuangxiang_dev`。具体密码由本人设置。不要手工建业务表，也不需要复制同学的数据库文件。

工程从 `backend/.env` 读取配置，进程环境变量优先。必须替换样例中的占位值：

| 配置 | 本地用途 |
| --- | --- |
| `DJANGO_SECRET_KEY` | 每台电脑独立生成的 Django 密钥 |
| `DJANGO_DEBUG=1` | 本地开发模式；不是公网配置 |
| `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost` | 本机允许的访问主机 |
| `DB_NAME`、`DB_USER`、`DB_PASSWORD` | 已建立的本机数据库、用户和密码 |
| `DB_HOST=127.0.0.1`、`DB_PORT=5432` | PostgreSQL 地址与端口 |
| `DJANGO_PUBLIC_ORIGIN=http://localhost:5173` | 前端开发地址 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 样例允许 `http://localhost:5173,http://127.0.0.1:5173` |
| `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` | 验证码邮件打印到后端终端，不真实发送 |
| `AI_ENABLED=0` | 关闭外部模型调用 |

生成本机密钥：

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

将结果填入 `.env` 的 `DJANGO_SECRET_KEY='实际生成值'`。真实配置、验证码、密码和密钥不放进 GitHub 或共享进度。无需填写 SMTP 账号，也不需要本地 Redis；开发使用文件缓存保存限流状态。

### 迁移和样例

先启动 PostgreSQL，再执行：

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py migrate --check
```

新增的 django-allauth 使用它自带的 `account` 迁移，同样由 `migrate` 应用；不要另外创建验证码表或在 User 中复制“邮箱已验证”字段。已有开发库也需要安装新依赖并执行迁移。

内部演示先初始化真实招募选项，再按[采集说明](ingestion-implementation.md)导入官方赛事并按[定时任务](maintenance.md)安排更新：

```powershell
.\.venv\Scripts\python.exe manage.py seed_recruitment_options
```

以下虚构样例命令仅用于隔离开发回归；带种子编码和虚构标记的赛事、招募与词表不进入正常公共页面。在 `DJANGO_DEBUG=1` 的隔离开发库执行：

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo_data
.\.venv\Scripts\python.exe manage.py seed_remaining_demo_data
.\.venv\Scripts\python.exe manage.py verify_database_schema
```

两条导入命令都只用于开发，重复运行保留已有内容，第二轮已有样例整批跳过。原始样例包含 15 个禁用虚构用户、29 条赛事，其中 26 条公开；以及后续模块的关联样例。实际数量会随人工试验改变，样例不是爬取结果，也不能作为真实通知发布。禁用样例账号不能直接登录。

`makemigrations` 是模型修改者生成新的迁移文件；`migrate` 是每位成员将已提交迁移应用到自己的数据库。拉取代码后不要重新生成已有 `0001`，不要删迁移或随意使用 `--fake`。当前用户模型始终为 `accounts.User`。

### 本机管理员

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

按提示输入自己的学校邮箱和独立强密码，仅用于本机开发后台；仓库不提供预设管理员凭据。后台创建用户已适配邮箱字段，不能手工把邮箱核验记录改为成功。网站的邮箱核验仍需走验证码流程。

## 日常启动与联调

保持 PostgreSQL 运行，在 `backend` 启动：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

再开一个终端，从仓库根目录进入前端：

```powershell
Set-Location .\frontend
npm.cmd ci
npm.cmd run dev
```

`npm ci` 只需在首次安装或锁文件变化后运行。日常直接 `npm.cmd run dev`。浏览器访问 <http://localhost:5173/>；后台访问 <http://127.0.0.1:8000/admin/>。页面通过 Vite 转发 `/api`，后端通过 ORM 查询本机 PostgreSQL；卡片模板早已写在前端，收到 JSON 后填入内容，不触发采集或 AI。

账号注册后可直接登录，但显示未验证。发送验证码后查看后端终端中的中文邮件，在**同一浏览器会话**输入验证码。保持前端地址一致，不在验证中切换 `localhost` / `127.0.0.1`，两者 Cookie 不共用。邮件只出现在本地终端；学校邮箱收不到是当前配置的预期行为。

两个开发终端都需保持运行，`Ctrl+C` 停止对应服务。`runserver` 仅供开发，不能按这个命令直接对公网开放。真实部署使用 [部署说明](deployment.md)，需要资源见 [费用清单](procurement.md)。

## 检查与测试

在 `backend` 执行：

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test --settings=config.test_settings
```

前三项分别检查配置、真实数据库连接、模型是否缺少迁移；测试配置使用临时 SQLite 数据库与内存邮件，不向真实邮箱发信，不修改开发库。SQLite 不能替代 PostgreSQL 的专用约束检查。

完整 PostgreSQL 测试在单独测试库运行：

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.postgres_test_settings --keepdb --noinput
```

测试库固定为 `test_` 加 `DB_NAME`。开发账号没有建库权限时，让本机数据库管理员预建该测试库并将所有者设为开发用户；不要为网站账号长期授予数据库超级权限。准备方式见 [数据库初始化](database-handoff.md#initialization)。测试会创建、修改并清空测试数据，测试库不能存放要保留的业务记录。

前端在 `frontend` 运行 `npm.cmd test` 与 `npm.cmd run build`。自动化覆盖账号、验证码、CSRF、权限、赛事服务/API/后台及模型；页面验收按 [人工验收](manual-checks.md) 另行完成。具体已通过结果记录在团队进度，不能用旧版测试数字代替改动后的验证。

## 代码与数据交接

| 文件或目录 | 作用与维护重点 |
| --- | --- |
| `config/settings.py`、`urls.py` | 配置、模块和根路由；修改后同步环境样例与接口说明 |
| `accounts/models.py`、`migrations/` | 用户及限制的模型基线；结构变化由数据库与后端共同确认 |
| `accounts/adapters.py`、`headless_urls.py` | 学校邮箱规则、allauth 注册/验证码适配、开放路由 |
| `accounts/views.py`、`permissions.py` | 本人资料与发布/申请账号门槛；不代替具体队伍权限 |
| `competitions/models.py`、`migrations/` | 赛事、来源及分类标签模型基线 |
| `competitions/serializers.py`、`views.py` | 公开字段白名单、分页筛选和详情 |
| `competitions/services.py`、`admin.py` | 草稿、来源核验、发布与下架的事务操作及后台表单 |
| `templates/account/email/` | 核验和密码找回邮件模板 |
| `ai_services/` | 后端内部 AI 调用，无独立 HTTP 接口 |
| `scripts/check_environment.py` | 只读验证实际数据库连接 |

数据库字段表与迁移继续作为基线；本轮没有另建一套用户、赛事或验证状态。后续接口改变字段含义时，先核对 [用户](database-fields.md#accounts)、[赛事](database-fields.md#competitions) 和 [队伍](database-fields.md#teams) 规则，再共同修改模型、迁移、接口与文档。

模型约束只处理底线。跨表写入、成员名额、状态变化与权限应放入服务层事务，必要时锁行；保存前执行 `full_clean()`。标准模型 `save()`、批量写入和 `M2M.add()` 不能自动替代这些检查。赛事服务已实现本轮操作，其他模块不能因为已有表就绕过服务层直接开放写入。

赛事后台默认保存草稿；补来源并确认原文后，选择发布动作。下架必须填写原因，产生操作记录。关联队伍的赛事暂拒绝下架，后续应把队伍状态、通知和赛事下架放在同一业务设计中接续；不要直接改字段绕过该限制。

<a id="email-integration"></a>

## 学校邮箱验证

已锁定 `django-allauth[headless]==65.19.4`。使用 `accounts.User`、Django Session、Cookie 与 CSRF；不维护第二套验证码或验证布尔列。允许未验证账号登录，新增招募/申请的账号资格另行要求学校邮箱已验证、账号正常、无有效限制且至少填写一种联系方式。

这个 allauth 版本的验证码模式要求配置 `ACCOUNT_EMAIL_VERIFICATION='mandatory'`；项目 Adapter 仅去掉登录阶段的邮箱阻断，使未验证用户能进入账号页主动发码。不能只看到配置名就断言未验证用户无法登录，也不能因此省略业务权限检查。

邮箱范围固定为精确域名 `tongji.edu.cn`，由 Adapter、模型校验与数据库约束共同保持一致；没有可单独改动的 `SCHOOL_EMAIL_DOMAINS` 开关。扩展域名需共同修改校验与迁移。

学校邮箱验证码是 6 位数字，本轮首次发送后 10 分钟有效、最多输错 5 次、最多重发 3 次。重发成功使旧码失效，不延长原有效期。另有邮箱与 IP 限流；当前参数与状态码详见 [API 说明](api.md)。找回密码使用 allauth 独立流程，复制邮件中的完整验证码，不假定也是 6 位数字。

当前只开放本人当前主邮箱核验，不提供邮箱自助换绑。用户后台的已有邮箱也设为只读；特殊换绑尚未实现，不能直接改 `User.email` 并沿用旧验证结果。新增管理员或历史用户首次登录网站时，会为完全缺失的 allauth 邮箱记录补建未验证主邮箱。

真实发信需项目持有或获准使用的 SMTP 服务。学校邮箱是收件地址，SMTP 账号是网站的发件身份，网站不收集学生的学校邮箱密码。后续取得资源后配置 TLS/SSL、发件地址并实际检查学校邮箱收件、延迟和垃圾邮件；开发终端出现邮件、自动化测试通过都不等于真实投递通过。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 找不到虚拟环境 Python | 确认当前在 `backend`，并已创建 `.venv` |
| 没有本轮页面或接口 | 核对分支及提交；本地整合、推送、合入 `main` 是不同状态 |
| 健康检查成功，列表失败 | 健康接口不查数据库；检查 PostgreSQL、连接配置和迁移 |
| `account_emailaddress` 等表不存在 | 安装当前依赖后执行 `migrate`，包括 allauth 自带迁移 |
| 学校邮箱没有收到验证码 | 免费开发版默认只打印到后端终端，不真实发送 |
| 注册/验证码提示太频繁 | 等待服务端冷却，不反复点击或关闭限流；共享网络可能共用 IP 配额 |
| 写入提示页面凭据失效 | 刷新取得 CSRF，检查前后端地址与可信来源；不要关闭 CSRF 中间件 |
| 端口已占用 | 使用空闲端口；前端端口变化同步可信来源，后端变化同步 `DEV_PROXY_TARGET` |
| 无法登录样例账号 | 样例用户故意禁用；在本机注册测试账号或单独创建管理员 |
| 关联队伍赛事无法下架 | 当前保护规则，等待组队状态联动实现，不直接绕过服务层 |

便携 PostgreSQL 用户可在 `backend` 使用 `scripts/database.ps1 status` / `start` / `stop`。此脚本依赖本人 `.local/postgresql-paths.json`，不是通用安装器；使用系统服务安装的同学按自己的服务管理方式启动数据库。
