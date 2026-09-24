# 用户字段表

版本：v1.0。用户已确认，作为当前分支的首版建模基线；用户模型、管理器和基础约束已编写，初始迁移尚未生成，待按交接流程同步后端。完整约束、权限及流程见 [用户字段说明](user-fields.md)。

## 用户基础表

模型 `accounts.User`，表名 `accounts_user`。本轮建立以下 12 个字段。邮箱用于登录；注册时额外联系方式可空，首次发布招募或提交申请前，微信号和手机号至少填一项，也允许同时填写。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认值或生成方式 | 主要约束 |
| --- | --- | --- | --- | --- | --- |
| `id` | 用户主键 | `BigAutoField` | 否 | 自动生成 | 主键，不修改 |
| `email` | 学校邮箱与登录标识 | `EmailField(254)` | 否 | 注册必填，无默认值 | 非空字符串；去首尾空格、全小写；唯一且忽略大小写；精确域名 `tongji.edu.cn` |
| `password` | 密码哈希 | Django 内置 `CharField(128)` | 否 | Django 密码接口生成 | 不保存明文，所有客户端接口均不返回 |
| `public_code` | 公开系统代号 | `CharField(11)` | 否 | 系统随机生成 | 唯一，`CX-` 加 8 位大写字母或数字；用户不可修改 |
| `wechat_id` | 微信号 | `CharField(64)` | 否 | 空字符串 `''`，`blank=True` | 非唯一；可修改；不保存二维码或图片 |
| `phone_number` | 联系手机号 | `CharField(32)` | 否 | 空字符串 `''`，`blank=True` | 非唯一；字符串存储；可修改；首期不做短信认证 |
| `contact_updated_at` | 联系资料修改时间 | `DateTimeField` | 是 | NULL，首次补充联系资料时写入 | 联系资料修改或邮箱换绑成功时由系统更新 |
| `is_active` | 账号是否启用 | `BooleanField` | 否 | True | 授权管理员维护；未验证或业务受限不改变此值 |
| `is_staff` | 管理后台入口资格 | `BooleanField` | 否 | False | 授权管理员维护，仍需具体操作权限 |
| `is_superuser` | 超级管理员标记 | `BooleanField` | 否 | False | 普通用户和学生内容管理员不默认开启 |
| `date_joined` | 注册时间 | `DateTimeField` | 否 | `timezone.now` | 创建时生成，普通用户不可修改 |
| `last_login` | 最近成功登录时间 | Django 内置 `DateTimeField` | 是 | NULL | 认证流程更新；无登录记录时为空 |

表中 `CharField(n)`、`EmailField(n)` 表示 `max_length=n`，不是可直接复制的模型构造代码。可选字符串只用 `''` 表示未填写；时间字段使用带时区时间，界面按 `Asia/Shanghai` 展示。

| 用户权限关系 | 关联对象 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `groups` | Django `Group`，多对多 | 空关系 | 由用户组授予内容维护、举报处理等权限 |
| `user_permissions` | Django `Permission`，多对多 | 空关系 | 个别用户的具体权限，由授权管理员维护 |

以上关系由 Django 管理关联表，不是用户表的普通列。移除默认的 `username`、`first_name`、`last_name`；队长或成员身份来自具体队伍关系。

## 业务限制记录

模型 `accounts.UserRestriction`，表名 `accounts_userrestriction`。治理阶段实现，不要求与第一轮用户基础表同时建表。

| 字段名 | 中文含义 | Django 类型 | 数据库可空 | 默认值或写入方式 | 主要约束 |
| --- | --- | --- | --- | --- | --- |
| `id` | 限制记录主键 | `BigAutoField` | 否 | 自动生成 | 主键 |
| `user` | 被限制用户 | `ForeignKey(User)` | 否 | 管理员操作指定的目标 | `on_delete=PROTECT`；一用户可有多条历史记录 |
| `reason` | 限制原因 | `CharField(500)` | 否 | 管理员必填 | 不允许空字符串，不公开 |
| `starts_at` | 限制开始时间 | `DateTimeField` | 否 | 系统当前时间 | 首版立即生效 |
| `expires_at` | 原定结束时间 | `DateTimeField` | 否 | `starts_at + 24 小时` | 固定时长，不开放自定义期限 |
| `created_by` | 处理管理员 | `ForeignKey(User)` | 否 | 当前授权操作者 | `on_delete=PROTECT`，客户端不可伪造 |
| `revoked_at` | 提前解除时间 | `DateTimeField` | 是 | NULL，提前解除时写入 | 自然到期无需填写 |
| `revoked_by` | 提前解除管理员 | `ForeignKey(User)` | 是 | NULL，提前解除时写入 | `on_delete=PROTECT`；与解除时间同时有值或同时为空 |
| `revoke_reason` | 提前解除原因 | `CharField(500)` | 否 | 初始 `''` | 人工提前解除时必填 |

外键的数据库列名由 Django 自动追加 `_id`。有效限制同时禁止新增招募和提交新申请，保留登录、已有记录、退出、申诉及已有成员关系。有效条件：当前时间处于开始与结束之间且未提前解除；到期自然恢复。重复处理同一有效限制不叠加或重置时长。

## 邮箱验证关联

复用 allauth `EmailAddress`，由后端锁定依赖并接入后使用其自带迁移。本表不重定义第三方模型的主键类型、长度或索引。

| 字段 | 含义 | 规则 |
| --- | --- | --- |
| `id` | 邮箱记录主键 | allauth 管理 |
| `user` | 所属用户 | 关联 `settings.AUTH_USER_MODEL` |
| `email` | 学校邮箱 | 当前生效主邮箱与 `User.email` 一致 |
| `verified` | 是否完成邮箱验证 | 新邮箱为 False；由验证流程更新，是验证状态唯一来源 |
| `primary` | 是否当前主邮箱 | 首期一个当前绑定主邮箱；换绑新邮箱需重新验证 |

## 展示及计算规则

| 项目 | 确定规则 |
| --- | --- |
| 公开资料 | 展示系统代号和学校邮箱验证标记；不公开邮箱、微信号或手机号 |
| 联系方式解锁 | 发起人接受申请后，仅对应双方可见学校邮箱及已填写的微信、手机号 |
| 联系资料更新 | 当前有联系权限的对象读取最新值；不以申请或成员表中的旧副本展示 |
| 联系权限结束 | 申请终止、撤回，或退出、移除完成后停止返回联系方式；招募关闭不影响已有成员的联系权限 |
| 未验证账号 | 可登录、查看公共内容及账号状态、重发验证码；不可发布招募或提交申请 |
| 计算状态 | `school_email_verified`、`has_contact_details`、`is_restricted`、`restriction_ends_at`、`can_publish`、`can_apply` 不新增同名数据库列 |
| 不新增的重复字段 | 不另存 `contact_email`，不设置只能二选一的 `contact_type`，不重复保存邮箱验证状态 |

本轮用户与赛事模型已编写。下一步同步后端，生成并检查初始迁移、在 PostgreSQL 空库验证、准备虚构样例数据，并配套 Admin 与业务写入流程。
