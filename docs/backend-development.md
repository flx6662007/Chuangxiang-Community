# 后端开发说明

## 当前范围

当前工程可以启动 Django/DRF 服务、响应健康检查，并通过辅助脚本验证 PostgreSQL 连接。用户模型、赛事模型和业务接口尚未实现，没有创建业务表，也没有采集或导入赛事数据。团队最新进度见 [团队进度](progress.md)。

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

当前只需空数据库，不要手工创建用户表、赛事表，也不要导入其他同学的真实个人数据。表结构将在模型和迁移完成后由 Django 创建。

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

当前启动时可能提示存在未应用迁移。用户模型尚未确定时保留该提示，先完成下文的首次迁移条件，不要为了消除提示而创建默认用户表。`/admin/` 此时不能正常登录或管理数据。

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
| `accounts/` | 账号业务模块；当前只有占位文件及迁移保护 |
| `competitions/` | 赛事业务模块；当前没有模型、查询接口或采集数据 |
| `scripts/check_environment.py` | 使用工程配置验证真实数据库连接 |
| `.env.example` | 展示所需配置项，供各自创建 `.env` |
| `requirements.txt` | 记录需要共同安装的 Python 依赖版本 |

`accounts` 和 `competitions` 属于一个后端工程，不是两个独立服务器。`migrations/` 用于保存模型变化生成的迁移文件，不存放数据库数据。

当前请求流程：浏览器访问 `/api/v1/health/` → `config/urls.py` 找到视图 → `config/views.py` 通过 DRF 返回固定 JSON。该接口无需登录，不访问数据库。

## 首次迁移

当前模型文件尚未定义平台业务模型。下一步按以下顺序完成：

1. 定义自定义用户 `accounts.User`，确认登录标识、邮箱唯一性等规则。
2. 在 `config/settings.py` 中配置 `AUTH_USER_MODEL = "accounts.User"`。
3. 定义本轮所需赛事模型，生成并检查初始迁移。自定义用户必须在 `accounts` 的首次迁移中创建。
4. 将模型、配置和迁移文件一起提交；其他开发者获取这些文件后，在自己的数据库执行迁移。
5. 迁移完成后，才创建管理员账号并使用管理后台。

模型已经实现、配置正确后，模型编写者可以生成迁移：

```powershell
.\.venv\Scripts\python.exe manage.py makemigrations accounts competitions
```

检查迁移内容后，再建表：

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

`makemigrations` 根据模型生成代码文件，`migrate` 将这些变化应用到数据库，两者不是同一步。当前 `migrate` 保护仅在用户模型仍为 `auth.User` 时阻止执行；正确实现并配置 `accounts.User` 后自然解除。不要只修改配置字符串而不定义模型，也不要删除保护来提前建表。

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
| 提示未应用迁移，或 `/admin/` 缺少表 | 按“首次迁移”完成模型、生成迁移、建表，不要提前迁移默认用户表 |
| 端口 `8000` 已占用 | 确认占用程序，或用 `runserver 127.0.0.1:8001` 并访问对应端口 |
