# 后端开发说明

## 当前范围

当前后端可以启动、响应健康检查，并通过辅助脚本验证 PostgreSQL 连接。用户模型、赛事模型、赛事列表、登录和邮箱验证尚未实现；没有创建业务表。

“工程骨架”指共同使用的代码目录、配置、依赖和运行入口。它与每台电脑上的 Python、虚拟环境和 PostgreSQL 共同构成开发环境。GitHub 保存代码与配置样例，每台电脑分别安装依赖、填写配置并保存开发数据。

## 已配置电脑启动

本机已经安装依赖并填写 `.env` 时，直接使用这一节。不要重新执行 `startproject`、`startapp`，不要覆盖现有 `.env`。

在仓库根目录打开 PowerShell：

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe manage.py test config
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

命令依次检查工程配置、验证实际数据库连接、运行骨架测试和启动开发服务。它们不创建业务表。运行环境检查和开发服务前，应先启动本机 PostgreSQL。

浏览器打开 <http://127.0.0.1:8000/api/v1/health/>：

```json
{"status":"ok","service":"chuangxiang-backend"}
```

访问根地址 <http://127.0.0.1:8000/> 会跳转到该接口。终端按 `Ctrl+C` 停止开发服务；PostgreSQL 是单独运行的进程，不会因此停止。

**此时不要运行 `migrate`、`makemigrations` 或 `createsuperuser`。** 当前暂未定义自定义用户模型，运行服务时可能提示有未应用的迁移，这是本阶段的已知状态。不能仅为消除提示而迁移默认用户表。`/admin/` 尚不能正常登录或操作数据。

## 新电脑准备

### 基础软件

准备 Python 3.13 的兼容补丁版本、PostgreSQL 17、Git 和编辑器。Python 依赖的精确版本以 `backend/requirements.txt` 为准。

使用数据库管理工具或 PostgreSQL 管理员账号，创建自己的开发数据库和登录用户，并把数据库所有者设为该用户。例如数据库名和用户名都可使用 `chuangxiang_dev`，密码自行设置。空数据库即可，当前不要手动创建用户表或赛事表。

每位开发者连接自己的数据库。Git 会同步模型和迁移文件，不会同步数据库中的记录或密码。

### Windows

以下命令用于首次配置的新电脑；如果已经克隆仓库，从进入 `backend` 开始：

```powershell
git clone https://github.com/flx6662007/Chuangxiang-Community.git
Set-Location .\Chuangxiang-Community\backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

如果终端不识别 `py`，使用所安装 Python 3.13 的完整路径替代它。后续始终使用 `.venv\Scripts\python.exe`，不依赖是否执行过虚拟环境激活脚本。

打开 `.env`，填写下一节中的本机值，然后执行“已配置电脑启动”中的命令。

### Linux

已安装 Python 3.13、venv 支持和 PostgreSQL 后，在 `backend` 目录执行：

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
```

填写 `.env`，启动 PostgreSQL 后执行：

```bash
.venv/bin/python manage.py check
.venv/bin/python scripts/check_environment.py
.venv/bin/python manage.py test config
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

以上是本地开发方式；Django 的 `runserver` 不用于正式上线。

## 本地配置

工程从 `backend/.env` 加载配置；已经设置的进程环境变量优先。不要把真实 `.env` 提交到 GitHub，也不要把同学的密码复制为自己的配置。

| 配置项 | 含义 | 本地填写方式 |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Django 使用的密钥 | 每台电脑自行生成，不使用样例占位值 |
| `DJANGO_DEBUG` | 是否显示开发调试信息 | 本地可设 `1`；未配置默认 `0` |
| `DJANGO_ALLOWED_HOSTS` | 接受请求的主机名 | 逗号分隔，默认 `127.0.0.1,localhost` |
| `DB_NAME` | 开发数据库名 | 填已创建的数据库 |
| `DB_USER` | 数据库登录用户 | 填该数据库的开发用户 |
| `DB_PASSWORD` | 数据库密码 | 填该用户的真实本机密码 |
| `DB_HOST` | 数据库地址 | 本机通常为 `127.0.0.1` |
| `DB_PORT` | 数据库端口 | 通常为 `5432`，按实际安装填写 |

Windows 可执行以下命令生成自己的密钥，再把结果填入 `.env` 的 `DJANGO_SECRET_KEY`：

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

密钥值建议用单引号包裹保存到 `.env`，避免其中的特殊字符影响读取。示例格式是 `DJANGO_SECRET_KEY='这里填写刚生成的值'`，不要填写这句示例文字。

### 本机 PostgreSQL 辅助脚本

`scripts/database.ps1` 只适用于已配置便携 PostgreSQL 路径的 Windows 电脑：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\database.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\database.ps1 start
```

需要停止时，把最后的 `start` 改成 `stop`。该脚本依赖本机 `backend/.local/postgresql-paths.json` 中的安装和数据目录；这个文件不提交。它不是 PostgreSQL 通用安装器。使用系统服务安装 PostgreSQL 的队友，应通过自己的服务管理方式启动数据库，无需运行该脚本。

## 文件怎么配合

| 文件或目录 | 作用 |
| --- | --- |
| `manage.py` | 运行 Django 检查、测试、服务等管理命令 |
| `config/settings.py` | 加载配置，启用 DRF 和业务模块，定义 PostgreSQL 连接 |
| `config/urls.py` | 把访问路径分发给对应处理函数 |
| `config/` 中的健康检查和测试 | 验证请求能进入后端并返回约定 JSON |
| `accounts/` | 预留账号业务；当前包含首次迁移保护 |
| `competitions/` | 预留赛事业务；模型和接口尚待实现 |
| `scripts/check_environment.py` | 使用真实工程配置连接 PostgreSQL 并执行查询 |
| `.env.example` | 展示需要填写的配置项，供队友建立自己的 `.env` |
| `requirements.txt` | 记录可共同安装的 Python 依赖版本 |

骨架最初由 Django 的 `startproject config .`、`startapp accounts`、`startapp competitions` 生成，再补充配置读取、PostgreSQL 连接、DRF 健康接口、迁移保护和文档。以上生成命令已经执行，克隆本仓库后不再重复执行。

健康检查的运行过程是：浏览器请求 `/api/v1/health/` → Django 路由找到接口 → DRF 返回固定 JSON。它无需登录，不查询数据库。真实数据库可用性由环境检查脚本验证，因此不能仅凭健康接口成功就判断数据库正常。

## 首次迁移的前置条件

当前 `accounts/models.py` 和 `competitions/models.py` 保持空白，未为平台建立业务迁移。

后续需要先完成以下条件：

1. 确定用户模型，定义 `accounts.User`，明确登录标识、邮箱唯一性等规则。
2. 在 `config/settings.py` 中指定 `AUTH_USER_MODEL = "accounts.User"`。
3. 为用户和赛事模型生成、检查并提交初始迁移；自定义用户模型必须在账号应用的首次迁移中创建。
4. 确认模型与迁移后，才在各自数据库应用迁移；之后再创建管理员。

为避免提前创建默认用户表，当前 `migrate` 命令在用户模型仍为 `auth.User` 时会明确拒绝执行。正确配置 `accounts.User` 后，保护条件自然解除，无需直接删除保护代码。仅修改配置字符串而没有实现对应模型，会导致工程启动失败。

## 常见问题

| 现象 | 处理方法 |
| --- | --- |
| 找不到 `.venv\Scripts\python.exe` | 确认当前目录是 `backend`，并已建立该目录下的虚拟环境 |
| 缺少配置或密钥无效 | 检查 `.env` 位置及内容，不能保留样例占位值 |
| PostgreSQL 连接被拒绝 | 检查服务是否启动、地址和端口是否正确 |
| 数据库认证失败或数据库不存在 | 对照本机数据库用户、密码、数据库名检查 `.env` |
| 健康接口可用，数据库检查失败 | 两者检查范围不同；修复数据库连接后再继续依赖数据库的功能 |
| 启动时提示未应用迁移 | 当前模型设计未完成时先保留该提示，不执行默认迁移 |
| 浏览 `/admin/` 报缺少表 | 管理后台尚未具备使用条件，先完成用户模型与初始迁移 |
| 端口 `8000` 已被占用 | 先停止占用进程，或使用 `runserver 127.0.0.1:8001` 并访问相应端口 |

本轮仍需实现赛事模型、公开列表接口和前端页面。健康检查通过只代表骨架具备继续开发的基础。
