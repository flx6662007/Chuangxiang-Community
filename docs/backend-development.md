# 后端开发说明

## 当前范围

当前工程可以启动 Django/DRF 服务、响应健康检查，并通过辅助脚本验证 PostgreSQL 连接。本分支已完成用户、赛事及本轮确认的后续业务模型，配置 `AUTH_USER_MODEL = 'accounts.User'`；本地共应用 35 项迁移、建立 58 张表并导入两轮虚构样例。Admin 表单、事务服务和业务接口尚未交付，没有采集或导入真实赛事数据。完整成果、复现命令和分工见 [数据库开发交付说明](database-handoff.md)，团队最新进度见 [团队进度](progress.md)。

“工程骨架”指项目代码目录、配置、依赖清单和运行入口。每台电脑还需安装 Python、依赖和 PostgreSQL，填写自己的配置。GitHub 同步代码和迁移文件，不同步虚拟环境、密码或数据库记录。

## 首次配置

### 1. 获取代码

新电脑需要 Python 3.13、PostgreSQL 17、Git 和编辑器。Python 依赖版本以 `backend/requirements.txt` 为准。

在准备存放项目的目录执行：

```powershell
git clone https://github.com/flx6662007/Chuangxiang-Community.git
Set-Location .\Chuangxiang-Community
```

新克隆的仓库默认使用 `main`，其中已包含基础工程和共享文档，无需切换到原骨架分支。

已有仓库无需重复克隆。先提交或妥善保存本地未提交改动，再在仓库根目录更新：

```powershell
git switch main
git pull --ff-only origin main
```

后续开发以更新后的 `main` 为起点创建自己的任务分支。

### 2. 准备数据库

使用 PostgreSQL 管理工具或管理员账号，创建自己的开发数据库和登录用户，并将数据库所有者设为该用户。数据库名和用户名可使用 `chuangxiang_dev`，密码自行设置。

先准备空数据库，不要手工创建用户表、赛事表，也不要导入其他同学的真实个人数据。获取迁移文件后由 Django 创建表结构，具体步骤见下文“首次迁移”。

### 3. 安装依赖

在仓库根目录执行一次 `Set-Location .\backend`。**后续配置、启动和检查命令都在 `backend` 目录执行，不要反复进入 `backend`。** 该目录应能看到 `manage.py` 和 `requirements.txt`。

Windows 首次配置：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

如果不识别 `py`，用已安装 Python 3.13 的完整路径替代它。后续直接使用虚拟环境中的 Python，不要求先运行激活脚本。已有 `.venv` 和 `.env` 的电脑不必重新创建或覆盖。

Linux 在同样的 `backend` 目录执行：

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
```

### 4. 填写配置

工程从 `backend/.env` 加载配置；已有的进程环境变量优先。打开该文件，填写自己的值，不提交到 GitHub。

| 配置项 | 含义与填写方式 |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django 密钥，每台电脑自行生成，不能保留占位值 |
| `DJANGO_DEBUG` | 本地开发可设 `1`，未配置默认为 `0` |
| `DJANGO_ALLOWED_HOSTS` | 允许的主机名，逗号分隔；默认 `127.0.0.1,localhost` |
| `DB_NAME` | 已创建的开发数据库名 |
| `DB_USER` | 该数据库的登录用户 |
| `DB_PASSWORD` | 该用户的真实本机密码 |
| `DB_HOST` | 数据库地址，本机通常为 `127.0.0.1` |
| `DB_PORT` | 数据库端口，通常为 `5432` |

Windows 生成密钥：

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

将结果填写为 `.env` 中 `DJANGO_SECRET_KEY='生成的值'`，单引号用于包裹实际密钥。Linux 将命令中的 Python 路径改为 `.venv/bin/python`。

完成后，先启动 PostgreSQL，再执行下文的“检查工程”。

## 日常启动

以下命令均在 `backend` 目录执行，前提是依赖和 `.env` 已准备好。不需要重新运行 `startproject` 或 `startapp`。

Windows：

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Linux：

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

访问 <http://127.0.0.1:8000/api/v1/health/>，应收到：

```json
{"status":"ok","service":"chuangxiang-backend"}
```

根地址 `/` 会跳转到该接口。这个响应不查询数据库，也不是赛事页面。按 `Ctrl+C` 停止开发服务，PostgreSQL 不会随之停止。`runserver` 仅用于本地开发，不用于正式部署。

新电脑在执行迁移前可能提示未应用迁移。用户模型与初始迁移已准备；先完成下文首次迁移步骤，再按需创建管理员。`/admin/` 尚未完成自定义用户和赛事管理适配。

## 检查工程

首次配置后或修改相关代码后按需检查，不必每次启动都完整执行。在 Windows 的 `backend` 目录运行：

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe manage.py test config
```

| 命令 | 检查范围 | 不代表什么 |
| --- | --- | --- |
| `manage.py check` | Django 配置和系统检查 | 不等于实际数据库连接成功 |
| `scripts/check_environment.py` | 用工程配置连接 PostgreSQL 并实际查询 | 不等于用户、赛事等业务表已创建 |
| `manage.py test config` | 当前骨架的健康检查与迁移保护测试 | 不等于业务功能已通过测试 |

Linux 将 Python 路径改成 `.venv/bin/python`，脚本路径使用 `scripts/check_environment.py`。环境检查前需启动 PostgreSQL。当前骨架测试不创建测试数据库；后续业务测试是否需要建库，以对应测试为准。

## 文件作用

| 文件或目录 | 当前作用 |
| --- | --- |
| `manage.py` | 执行 Django 检查、迁移、测试和开发服务命令 |
| `config/settings.py` | 读取配置，启用模块，配置数据库及 DRF |
| `config/urls.py` | 将请求路径交给对应处理代码 |
| `config/views.py` | 处理健康检查并返回 JSON |
| `config/tests.py` | 检查健康接口和首次迁移保护 |
| `accounts/` | 邮箱登录用户模型、用户管理器、基础校验及迁移保护；邮箱验证和接口待开发 |
| `competitions/` | 赛事届次、来源、分类标签模型及基础校验；事务写入和接口待开发 |
| `scripts/check_environment.py` | 使用工程配置验证真实数据库连接 |
| `.env.example` | 展示所需配置项，供各自创建 `.env` |
| `requirements.txt` | 记录需要共同安装的 Python 依赖版本 |

`accounts` 和 `competitions` 属于一个后端工程，不是两个独立服务器。`migrations/` 用于保存模型变化生成的迁移文件，不存放数据库数据。

当前请求流程：浏览器访问 `/api/v1/health/` → `config/urls.py` 找到视图 → `config/views.py` 通过 DRF 返回固定 JSON。该接口无需登录，不访问数据库。

## 首次迁移

本轮已定义用户、赛事及全部已确认的后续模型，配置自定义用户，生成完整迁移链。本机和独立空库的迁移与样例验证已完成，文件随数据库分支交付，待团队审核。队友获取全部迁移文件后直接执行：

```powershell
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py seed_demo_data
.\.venv\Scripts\python.exe manage.py seed_remaining_demo_data
.\.venv\Scripts\python.exe manage.py verify_database_schema
```

两条 `seed` 命令仅用于 `DJANGO_DEBUG=1` 的开发环境，重复运行保留原有记录；第二轮已有样例整批跳过，不自动补造历史。`verify_database_schema` 只读检查实际结构。迁移完成后，可按后端接续需要使用 `createsuperuser` 创建管理员；虚构样例账号全部不可登录，Admin 表单仍待适配。

`makemigrations` 根据模型生成代码文件，`migrate` 将这些变化应用到数据库，两者不是同一步。后续修改模型时再生成新的迁移；队友无需重新生成已有 `0001`。当前 `migrate` 保护仅在用户模型仍为 `auth.User` 时阻止执行，配置 `accounts.User` 后自然解除。完整初始化、样例范围与测试库准备见 [数据库初始化与验收](database-handoff.md#initialization)。

## 模型阶段测试与写入约定

在 `backend` 目录运行隔离测试：

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.test_settings
```

该配置仅用于自动化测试，在临时 SQLite 内存库执行真实迁移，不读取或修改本机 PostgreSQL 数据。本轮共 108 项，106 项通过、2 项 PostgreSQL 专用检查跳过。

PostgreSQL 验收使用独立测试库及真实迁移，108 项全部通过。本机已预建 `test_chuangxiang_dev`，可运行：

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.postgres_test_settings --keepdb --noinput
```

其他电脑的测试库命名及权限准备见 [初始化说明](database-handoff.md#initialization)。

用户创建使用 `User.objects.create_user` / `create_superuser`，保证邮箱规范化、密码强度校验与哈希。`User.save()` 会执行基础验证并维护联系资料时间。已有 Django 认证后端可以按邮箱识别用户，但注册、登录、学校邮箱验证和资料权限的 HTTP 接口尚未实现。

赛事及新增业务模型需由后端统一写入服务在事务中调用 `full_clean()` 后保存；Django 标准 `save()` 不会自动执行它，批量写入及 `M2M.add()` 同样绕过 Python 校验。数据库约束处理字段底线，跨表发布、主来源切换、版本和多选装配、名额并发、核验身份及权限仍需服务层实现。当前未注册 Admin 管理类；自定义用户表单须适配邮箱字段和系统代号，不能直接复用带 `username` 的默认字段集。详见 [赛事实现边界](database-fields.md#competitions)、[后续字段说明](database-fields.md#teams)及 [交付边界](database-handoff.md)。

## PostgreSQL 辅助脚本

`scripts/database.ps1` 仅供已配置便携 PostgreSQL 路径的 Windows 电脑使用。在 `backend` 中执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\database.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\database.ps1 start
```

需要停止时，将最后的 `start` 改为 `stop`。脚本依赖本机 `backend/.local/postgresql-paths.json`，该文件不提交。因此它不是通用安装器；通过系统服务安装 PostgreSQL 的电脑，应使用自己的服务管理方式，不必运行此脚本。

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 仓库中没有 `backend` | 确认使用本项目仓库，并按“获取代码”更新 `main`；若仍缺少目录，检查 `git pull` 的提示 |
| 找不到 `.venv\Scripts\python.exe` | 确认当前目录是 `backend`，且已创建该目录下的虚拟环境 |
| 缺少配置或密钥无效 | 检查 `backend/.env`，替换样例占位值 |
| PostgreSQL 连接被拒绝 | 检查数据库是否启动、地址和端口是否正确 |
| 数据库认证失败或数据库不存在 | 检查数据库名、用户名、密码及用户权限 |
| 健康接口正常，数据库检查失败 | 两者检查范围不同，需单独修复数据库连接 |
| 提示未应用迁移，或 `/admin/` 缺少表 | 获取本分支迁移文件后按“首次迁移”执行 `migrate`；Admin 表单另需后端适配 |
| 端口 `8000` 已占用 | 确认占用程序，或用 `runserver 127.0.0.1:8001` 并访问对应端口 |


<a id="email-integration"></a>

## 学校邮箱验证接入

学校邮箱登录与验证规则已确认，状态归属见[用户与邮箱规则](database-fields.md#email-verification)。后端使用 django-allauth Headless、Django Session、Cookie 和 CSRF 接入页面。当前未安装或接入 allauth；验证码参数、发信和真实收件尚未完成。

### 当前账号基础

| 内容 | 当前代码与行为 |
| --- | --- |
| 用户模型 | [accounts/models.py](../backend/accounts/models.py) 定义 `accounts.User`，继承 `AbstractUser`，移除 `username`、`first_name`、`last_name`，以 `email` 为登录标识 |
| 全局配置 | [config/settings.py](../backend/config/settings.py) 已设置 `AUTH_USER_MODEL = 'accounts.User'`；保留 SessionAuthentication、Session 和 CSRF 中间件 |
| 邮箱规范化 | [accounts/managers.py](../backend/accounts/managers.py) 将邮箱去首尾空白并转为小写；模型保存同样规范化；邮箱登录查询使用相同规则 |
| 学校邮箱范围 | [accounts/validators.py](../backend/accounts/validators.py) 校验邮箱格式和精确域名 `tongji.edu.cn`；伪造后缀不被接受 |
| 邮箱唯一性 | `email` 普通唯一约束、`Lower(email)` 唯一约束，以及规范化和学校域名检查约束已定义 |
| 密码 | `create_user` / `create_superuser` 执行密码强度校验，通过 Django 密码接口生成哈希；模型校验拒绝普通明文密码写入 |
| 系统代号 | 自动生成固定的 `CX-` 加 8 位大写字母或数字，必填且唯一；碰撞时有限重试，不接受创建入口传入自定义代号 |
| 联系资料 | 注册时微信、手机号可空；用户模型提供 `has_contact_details` 并维护联系资料更新时间；发布、申请前的业务门槛待接口接入 |
| 验证状态 | 当前 User 没有额外的“已验证”布尔列，也没有临时验证码表 |

上述是模型和基础配置，不代表网站注册、登录或邮箱验证接口已经可用。本地初始迁移与 PostgreSQL 建表验证已完成，开发库仅导入不可登录的虚构用户，没有创建真实用户；Admin 表单也待适配。

当前没有接入 `SCHOOL_EMAIL_DOMAINS` 配置。允许域名在模型校验和数据库约束中固定为首版规则；后端 Adapter 应复用同一规则。将来若扩展域名，必须同步修改校验与数据库约束迁移，不能只增加环境变量。

### 待接入的邮箱验证流程

#### 1. 确定并锁定 allauth 版本

当前依赖中尚无 django-allauth。后端先核对与 Django 5.2、Headless、验证码及未验证账号登录策略的兼容性，再将实际采用版本锁定到项目依赖。

优先使用 allauth 的账号和验证码能力，不同时维护第二套注册或验证状态系统。具体配置项及路由随锁定版本在 [API 说明](api.md) 中登记，本文不把未验证的配置样例作为现成实现。

#### 2. 接入注册与登录

- 注册校验精确学校域名、邮箱规范化和唯一性；通过 Django 密码接口存储密码。
- 账号接口使用 `accounts.User`，其他业务外键使用 `settings.AUTH_USER_MODEL`。
- allauth 的实际创建路径也必须满足现有模型约束；不能假设它必然调用自定义 `create_user`，需通过集成测试验证。
- 已存在但未验证的邮箱再次注册时，不创建第二个账号、不覆盖原密码或资料；引导登录、重发或找回流程，响应与限流由后端统一处理。
- 使用允许未验证账号登录的验证策略，并实际联调 Headless 和验证码流程。

#### 3. 维护唯一的邮箱验证状态

验证结果只使用 allauth 的 `EmailAddress`，不在 User、申请表或成员表复制验证布尔值。业务读取时，须同时满足：

1. 邮箱记录属于当前用户。
2. 规范化后的邮箱与当前 `User.email` 一致，且域名在允许范围内。
3. 记录为当前主邮箱，且 `verified=True`。

首期每个账号只有一个当前生效的绑定主邮箱。特殊换绑由管理员处理，新邮箱须重新验证；不得直接修改 `User.email` 后继承旧邮箱的验证结果。换绑成功时同步用户邮箱、allauth 主邮箱记录和联系资料更新时间。

#### 4. 接入邮件验证码

由 allauth 负责验证码生成、有效期、尝试限制和验证结果更新。验证码位数、有效期、尝试次数、重发冷却及发送限流需结合锁定版本统一配置并联调；早期方案中的示例数值不视为当前代码配置。

验证流程必须覆盖正确、错误、过期、重复使用、重发、频率限制和发信失败。新旧验证码的失效规则应以最终配置和测试结果写入 API 契约，避免前后端理解不同。

#### 5. 接入业务权限

服务端在每次发布招募、提交申请时检查：已登录、账号启用、当前学校邮箱已验证、没有有效业务限制、微信号或手机号至少补齐一项，以及赛事、队伍、名额等对象条件。

`is_active` 表示账号是否启用，不用于表示邮箱是否验证或是否处于 24 小时业务限制。前端隐藏按钮不能替代服务端检查。联系方式仅按已经确认的关系权限返回，不放入公开接口。

### 开发发信与真实联调

接入验证流程时，先使用 Django Console Email Backend 在本机查看邮件内容。它只用于开发验证，不证明真实学校邮箱能够收件；当前代码尚未配置这条验证码发信流程。

真实联调使用项目掌控的发件邮箱或邮件服务，确认提供商后配置 SMTP 或邮件 API。只在 `.env.example` 记录参数名称和安全占位值；真实密码、授权码、API key 留在本机或服务器环境配置中，不提交 Git。

使用 SMTP 时通常需配置邮件后端、主机、端口、发件账号、密码、TLS/SSL 和默认发件地址。具体数值由选定服务决定，本文不写入实际凭据。真实联调须覆盖同济邮箱收件、延迟、垃圾邮件、重发及服务失败。

### 验证结果与后续验收

当前 108 项测试在独立 PostgreSQL 测试库通过；SQLite 离线测试 106 项通过、2 项 PostgreSQL 专用检查跳过。它们没有验证 allauth、账号 HTTP 接口、验证码或真实发信；数据库复现结果见 [初始化与验收](database-handoff.md#initialization)。

后续按下面的范围验收：

| 阶段 | 需要通过的检查 |
| --- | --- |
| PostgreSQL 初始化 | 自定义用户在 accounts 首次迁移中建立；空库可迁移；邮箱唯一、大小写、域名及必填约束有效 |
| allauth 接入 | 注册使用现有用户模型；重复邮箱不能覆盖账号；初始未验证；未验证用户可登录但不能发布或申请 |
| 验证码 | 正确验证码生效；错误、过期、重复使用、重发、尝试次数与发送限流符合约定 |
| 验证状态一致性 | 当前主邮箱与 User.email 一致；换绑不能继承旧验证结果；不存在两份互相冲突的验证状态 |
| Session / CSRF | 登录、退出及刷新行为正确；需要保护的写操作执行 CSRF 校验 |
| 业务权限 | 邮箱验证之外继续检查账号限制、联系方式和对象条件；公开接口不返回私有联系方式 |
| 真实发信 | 项目发件服务可向学校邮箱投递；失败响应和重试策略明确 |

### 接续职责

数据库侧已完成已确认模型的迁移、PostgreSQL 空库建表、约束和虚构样例验证，随数据库分支交付，待后端审阅。allauth 使用其锁定版本自带的迁移，不由数据库侧仿建第三方验证码或邮箱状态表。

后端接入 allauth、Adapter、Session、验证码与邮件配置、权限、限流和账号接口，并适配邮箱登录的 Admin 表单。前端按实际 API 契约接入注册、登录、验证码、重发和状态提示。

本文随账号功能进展维护；新增接口及实际配置记录到 [API 说明](api.md)，完成情况记录到 [团队进度](progress.md)。
