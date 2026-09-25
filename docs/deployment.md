# 部署说明

## 当前状态

本轮先完成**零付费、本机可演示的开发版本**。Windows 上继续使用本地 Python、PostgreSQL、Node.js；本地邮件可输出到开发终端，不能据此宣称已向学校邮箱发信，也不能证明使用者拥有该邮箱。自动化测试不会购买服务或发送真实邮件。

下面准备的是之后供其他同学访问的部署方案：Linux + Docker Compose + Caddy + Django/Gunicorn + PostgreSQL + Redis + SMTP。部署文件已提供；目前没有服务器、域名和发件服务，**未公网部署，未验证真实邮件投递**。本机没有 Docker，本次未执行镜像构建和容器运行；上线前必须在目标 Linux 主机完成本页检查。

可先申请学校已有服务器、现有域名的子域名和获准使用的发件服务，减少新增费用。缺少资源时继续本地开发，不自动开通付费项目。后续采购项见 [资源清单](procurement.md)。

当前本机演示按 [后端开发说明](backend-development.md) 与 [前端启动说明](../frontend/README.md) 启动；本页后续 Linux、Docker、域名和 SMTP 步骤留到获得资源后执行。本地终端验证码只用于开发演示，不把该模式直接开放给真实用户使用。

## 运行方式

```text
同学的浏览器
    │ https://你的域名
    ▼
Caddy：HTTPS、前端静态网页、路径分发（仅 80/443 对外）
    ├─ /api/*、/admin/* → Gunicorn → Django
    │                                  ├─ PostgreSQL：业务与账号数据
    │                                  ├─ Redis：各进程共享的限流缓存
    │                                  └─ SMTP：向学校邮箱发送验证码
    ├─ /static/* → Django 管理后台静态文件
    └─ 其他路径 → Vue 页面；刷新子页面也能打开
```

网页与接口共用同一个域名，前端请求相对地址 `/api/v1/`，登录使用 `/api/auth/browser/v1/`。不把数据库地址、SMTP 密码或 AI 密钥放进前端。PostgreSQL、Redis、Gunicorn 均不映射服务器公网端口；Caddy 保留请求路径并重写代理头，Django 才信任该代理给出的 HTTPS 状态。`ALLAUTH_TRUSTED_PROXY_COUNT=1` 对应这一层 Caddy，使账号限流按实际来访地址计数。

| 文件 | 作用 |
| --- | --- |
| `compose.yaml` | 启动四个服务，配置网络、持久卷、健康检查与日志大小 |
| `deploy/backend.Dockerfile` | Python 3.13 + Gunicorn；后端以普通用户运行 |
| `deploy/web.Dockerfile` | 用 Node 24 构建前端，再由 Caddy 提供网页 |
| `deploy/Caddyfile` | HTTPS、反向代理、后台静态文件及前端路由回退 |
| `deploy/.env.example` | 服务器配置样例；实际值写入不入库的 `deploy/.env` |
| `deploy/postgres/10-create-app.sh` | 首次初始化时建立普通数据库应用账号和数据库 |
| `backend/requirements-production.txt` | 通用依赖之外的 Gunicorn 与 Redis Python 客户端 |

数据库迁移、静态文件收集、管理员创建均由部署人员明确执行一次。启动服务不会自动导入虚构样例，也不内置管理员密码。API 健康检查只证明 HTTP 服务可响应，业务数据库还需查询接口和迁移检查验证。

## 准备资源

1. 一台获准使用、能够安装 Docker 的 Linux 主机；建议先用 Ubuntu 24.04 LTS。小范围试点可从 2 核、4 GB 内存评估起步，实际容量以构建、并发和数据库测试为准，这不是性能承诺。
2. 可管理 DNS 的域名或子域名；将 A 记录指向服务器公网 IPv4。仅在服务器 IPv6 确实可访问时配置 AAAA。
3. 可用于验证码的 SMTP 服务及获准使用的发件地址。学校提供的发件服务也可以，只要允许该网站程序使用并能满足试点额度。
4. 域名管理员、服务器管理员、发件服务管理员明确到人；密钥保存在服务器配置或团队密码管理工具中。

只允许 Caddy 对公网开放 TCP 80/443（可选 UDP 443）。SSH 按服务器管理要求限制来源；不要开放 5432、6379、8000。采用 Docker 端口映射时同时检查云安全组与主机规则，不能只根据 UFW 显示结果认定端口已受保护。Docker 官方安装说明提醒了这一点。[Docker Ubuntu 安装与端口说明](https://docs.docker.com/engine/install/ubuntu/)

## 邮件是什么

SMTP 是网站向邮件服务提交邮件的接口。学校邮箱是**收验证码的地址**；项目发件服务是**代网站发验证码的账号**。同学注册时只提供邮箱地址和验证码，不向网站提供学校邮箱密码。

邮件服务商提供 SMTP 地址、端口、专用密码或令牌以及发件身份。域名发件服务通常会给出域名所有权、SPF、DKIM 等 DNS 记录；按所选服务的实际说明配置并验证，不照抄其他服务商的记录值。确认发件地址、额度、速率、失败记录和学校收件方的实际投递情况。

`EMAIL_USE_TLS=1` 通常配合 587；`EMAIL_USE_SSL=1` 通常配合 465。以服务商要求为准，两者不能同时开启。生产配置固定 SMTP 后端，不能用“终端打印验证码”冒充真实发信。拿到资源后，先给团队自己的测试邮箱投递，再开放注册。

## 首次安装

以下命令在 **Linux 服务器的 Bash 终端**执行；不是 Windows PowerShell 命令。

先按 [Docker 官方 Ubuntu 安装步骤](https://docs.docker.com/engine/install/ubuntu/) 安装 Docker Engine 与 Compose 插件，不复制不明来源的一键脚本。然后检查：

```bash
sudo docker version
sudo docker compose version
git clone https://github.com/flx6662007/Chuangxiang-Community.git
cd Chuangxiang-Community
```

选择已通过团队验收、包含本部署文件的提交。记录 `git rev-parse HEAD`，以便后续回退；不要在服务器直接修改业务代码。

```bash
cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
nano deploy/.env
```

填完每一个 `replace-with-...`；`DOMAIN` 只填域名，不填 `https://`。四类密钥分别生成，不复用学校邮箱密码。可在可信本机用 Python 的 `secrets.token_urlsafe(48)` 生成随机串；生成值只写入配置，不发进聊天或 GitHub。

`DB_USER` 必须使用普通应用账号（默认 `chuangxiang_app`），不能改为 `postgres`。`POSTGRES_PASSWORD` 是独立的数据库管理密码。Redis 密码采用 URL 安全字符，因为 Compose 会用它拼接 `REDIS_URL`。SMTP 密码如包含 `$`、`#`、空格等，按 Compose `.env` 规则使用单引号包裹，不将整个文件用 `source` 执行。配置文件权限 600 只是基础措施，服务器和 Docker 管理权限同样需要控制。

后续命令使用简写函数；重新登录终端后需要重新定义。`config --quiet` 只校验而不打印包含密钥的完整展开配置：

```bash
dc() { sudo docker compose --env-file deploy/.env "$@"; }
dc config --quiet
dc build --pull backend web
dc up -d --wait db redis
dc run --rm --no-deps backend python manage.py check --deploy
dc run --rm --no-deps backend python manage.py migrate --noinput
dc run --rm --no-deps backend python manage.py migrate --check
dc run --rm --no-deps --user root backend chown 10001:10001 /app/staticfiles
dc run --rm --no-deps backend python manage.py collectstatic --noinput
dc run --rm --no-deps backend python manage.py createsuperuser
dc run --rm --no-deps web caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
dc up -d --wait backend web
dc ps
```

逐条确认成功再继续。`chown` 只在初始化静态文件卷时以容器 root 执行一次；网站服务仍以普通用户运行。`check --deploy` 如有警告需逐项处理；新域名在 HTTPS 完整验证前不要贸然启用长期 HSTS。管理员使用本人学校邮箱和独立强密码创建。首次数据库初始化只对空卷生效：日后只修改 `.env` 不会自动修改已有数据库账号密码或库名。

Caddy 根据域名申请和续期证书，要求 DNS、80/443 连通性及证书机构访问条件满足要求；持久化 `/data`，避免反复丢失证书状态。遇到证书失败先检查解析及网络，不反复删除卷。[Caddy 自动 HTTPS](https://caddyserver.com/docs/automatic-https)

## 上线检查

下面的测试在实际服务器配置完后进行，不能用本地自动化通过代替：

| 检查 | 正常结果 |
| --- | --- |
| 换一台电脑或手机网络访问域名 | HTTPS 可用，证书域名正确，首页与刷新子页面正常 |
| 访问 HTTP 地址 | 自动跳到 HTTPS |
| 赛事列表及详情 | 从生产数据库读取公开数据；没有虚构测试内容 |
| 后台及 `/static/admin/css/base.css` | 后台登录页样式正常，只有有权限的账号能操作 |
| 无权限直接请求接口 | 被后端拒绝，隐藏按钮不能代替权限检查 |
| 注册学校邮箱、输入收到的验证码 | 收件箱真实收到，验证成功；验证码错误、过期、重发和限流符合接口约定 |
| 普通邮箱注册 | 被学校邮箱规则拒绝；学校规则与当前数据库约束一致 |
| 注销后刷新、无痕窗口访问 | 不继续保留已登录操作权限 |
| 重启后端后再访问 | 账号、赛事数据和数据库会话保留，共享缓存可连接 |
| 外网探测数据库、Redis 和 8000 端口 | 无公网映射，不能直接连接 |

先用 Django 自带命令向**自己的测试邮箱**发送一封测试邮件：

```bash
dc exec backend python manage.py sendtestemail 你的测试邮箱@tongji.edu.cn
```

再用网页完成真实注册验证。命令成功仅表示 SMTP 接受请求；收件、垃圾邮件箱及验证码流程要实际确认。不要为试验向无关同学批量发信。

排障命令：`dc logs --tail 100 backend web`、`dc ps`。分享日志前去掉邮箱、请求参数和其他个人信息。容器没有配置控制台邮件后端，不应在生产日志里打印验证码或密钥。

## 备份与升级

数据库、Redis、证书和后台静态文件分别使用持久卷。`docker compose down` 默认保留卷；**不要添加 `-v`，否则会删除这些持久数据**。正式数据与开发样例分库，不把真实注册信息放进 GitHub。

业务数据用 PostgreSQL 逻辑备份；在项目之外创建仅管理员可读的备份目录。下面示例需在项目根目录、已定义 `dc` 的同一 Bash 会话运行：

```bash
umask 077
backup_dir="$HOME/chuangxiang-backups"
mkdir -p "$backup_dir"
backup_file="$backup_dir/chuangxiang-$(date -u +%Y%m%dT%H%M%SZ).dump"
if dc exec -T db sh -c 'pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc' > "$backup_file.tmp"; then
  mv "$backup_file.tmp" "$backup_file"
  printf '备份完成：%s\n' "$backup_file"
else
  printf '备份失败，.tmp 文件不能用于恢复\n' >&2
fi
```

至少在每次升级前备份，并根据实际使用量设定每日备份和保留周期。将备份加密保存到另一台受控设备；只放在同一台服务器不能应对服务器丢失。`deploy/.env` 另行加密备份，它不包含在 `pg_dump` 中。

恢复应先在隔离的测试数据库演练，验证成功后再决定生产切换。下面命令建立独立恢复库，不覆盖正在使用的 `DB_NAME`；`chuangxiang_restore_check` 必须是尚不存在的新库：

```bash
dc exec -T db sh -c 'createdb -U postgres -O "$DB_USER" chuangxiang_restore_check'
dc exec -T db sh -c 'pg_restore --exit-on-error --no-owner --no-privileges -U "$DB_USER" -d chuangxiang_restore_check' < "$backup_file"
```

再在隔离服务环境中指向该恢复库，运行迁移检查并核对赛事、用户和权限；没有完成恢复演练不能仅凭备份文件存在就认定可恢复。恢复库包含真实个人信息，演练后由管理员按数据保留规则清理。

升级顺序：通知短时维护 → 备份 → 获取已验收的指定提交 → 构建镜像 → 停止网页和后端 → 迁移与收集静态文件 → 启动 → 完成核心流程检查。小团队先采用明确的短时维护，不声称零停机：

```bash
git fetch origin
# 在此选择并检出已验收的提交，记录升级前后的提交号。
dc build --pull backend web
dc stop web backend
dc run --rm --no-deps backend python manage.py migrate --noinput
dc run --rm --no-deps backend python manage.py collectstatic --noinput
dc up -d --wait backend web
```

迁移失败立即停止后续步骤并检查原因。代码回退不等于数据库回退：有不兼容迁移时，需要按已演练的恢复方案处理；恢复到备份会丢失备份后的写入。PostgreSQL 大版本升级单独制定迁移方案，不能直接将已有卷从 17 换成其他大版本。

## 验证边界与参考

本轮已通过 YAML 解析、环境变量引用与配置样例对照、构建文件及挂载路径检查；确认仅 Web 服务配置公网映射；PostgreSQL 初始化脚本通过 Bash 语法检查。这些是静态检查，不等于 `docker compose config`、镜像构建或实际部署通过。

本轮提供的是可供目标服务器验证的部署配置。没有 Docker 运行环境、真实域名和 SMTP 凭据时，不能证明容器已启动、证书已签发、邮件已送达或公网容量达标。实际启动后把部署提交号、服务器环境、日期和检查结果补入团队进度表。

前端按 [Caddy 的 SPA 与 API 分流方式](https://caddyserver.com/docs/caddyfile/patterns) 配置；[反向代理头说明](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) 用于确认 HTTPS 与客户端地址的传递。依赖服务通过 [Compose 健康条件](https://docs.docker.com/compose/how-tos/startup-order/) 控制启动顺序；[Gunicorn](https://pypi.org/project/gunicorn/26.2.0/) 用于 Linux WSGI 服务。生产版本使用固定 Gunicorn/Caddy 版本和前端锁文件；Python、Node、PostgreSQL、Redis 的镜像仍按主版本标签取维护更新，上线时记录实际镜像摘要，更新后重新测试。
