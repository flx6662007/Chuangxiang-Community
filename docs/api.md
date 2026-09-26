# API 说明

本文对应当前实现。普通业务接口使用 `/api/v1/`，账号认证使用 `/api/auth/browser/v1/`。**认证路径末尾没有 `/`，普通业务路径末尾有 `/`**，按表中路径请求。

游客可读公开赛事和招募卡。本人资料、申请、队伍与通知需要登录；写入使用 Session Cookie 与 CSRF。组队路径、固定模板、权限、版本和状态详见 [组队接口](api-teams.md)。采集通过管理命令与 Admin 运行；科研、资源、快讯和 AI 的公共 HTTP 接口尚未开放。AI 内部调用见 [AI 服务说明](ai-services.md)。

## 请求约定

- JSON 写请求发送 `Content-Type: application/json`，浏览器保留 Session Cookie。
- 首次写入前调用 `GET /api/v1/accounts/csrf/`。每次写入从当前 `csrftoken` Cookie 读取 `X-CSRFToken`；登录会轮换 CSRF，不能一直复用旧值。
- 开发时通过前端的 `/api` 代理请求，避免分别配置跨域认证。不要把 Cookie 或密码存入 `localStorage`。
- 文本空值通常为 `""`，未知日期、时间与可空对象为 `null`；多项关联为空时为 `[]`。
- 日期是 `YYYY-MM-DD`，时刻是带时区的 ISO 8601 字符串。只有日期不代表当天 00:00 或 23:59；显示时结合相应时区与说明，不补造时刻。

## 健康检查

`GET /api/v1/health/`，无需登录，成功为 `200`：

```json
{"status":"ok","service":"chuangxiang-backend"}
```

不查询数据库，也不验证邮件或 AI。根路径 `/` 重定向到该接口，非读取方法返回 `405`。数据库连接用 `scripts/check_environment.py` 单独检查。

## 赛事查询

### 列表

`GET /api/v1/competitions/`，无需登录。只返回 `published` 且非固定虚构种子的赛事。明确尚未过报名日期或仍开放平台招募的记录优先，随后按主来源原通知发布日期、平台首次发布时间和 ID 倒序；原通知日期未知的排在同组已知日期后。采集时间不冒充通知发布时间。搜索与分类可组合。

| 参数 | 规则 |
| --- | --- |
| `page` | 页码，默认 1；无效或越界页返回 404 |
| `page_size` | 正整数，默认 20，最大 50；超过 50 按 50，非法值返回 400 |
| `search` | 最多 200 字符，去首尾空白；匹配标题、简介或主办方 |
| `category` | 分类 `code`，最多 64 字符；精确匹配，无匹配返回空列表 |
| `recruitment_open` | `true` / `false`（兼容 `1` / `0`）；筛选赛事是否开放站内招募，不能据此推断官方报名状态 |

分类词表：`GET /api/v1/competitions/categories/` 返回启用分类数组，例如 `[{"id":1,"code":"engineering","name":"工程"}]`。分类、标签与赛事范围集合：`GET /api/v1/competitions/options/` 返回 `{categories:[], tags:[], levels:[]}`；词条含 `id/code/name`，范围含 `code/name`。两接口均允许游客只读，停用项不供新选择，历史记录仍保留名称。

响应结构：

```json
{"count":0,"next":null,"previous":null,"results":[]}
```

`next`、`previous` 有下一页或上一页时为完整 URL，否则为 `null`。首次页无匹配结果正常返回 `200`。每个 `results` 项包含：

| 字段 | 类型与含义 |
| --- | --- |
| `id`、`code` | 整数主键、稳定赛事编码；详情使用 `id` |
| `title`、`edition`、`summary` | 标题、年度/届次、列表简介 |
| `category` | `{id, code, name}` 或 `null` |
| `tags` | `{id, code, name}` 数组 |
| `level`、`participation_type` | 模型枚举值，含未知状态；取值见 [赛事字段说明](database-fields.md#competitions) |
| `organizer` | 主办方文本 |
| `registration_deadline` | 报名截止日期或 `null` |
| `registration_deadline_at` | 已知的精确截止时刻或 `null` |
| `registration_deadline_timezone` | 原通知时区，未知为空串 |
| `published_at`、`updated_at`、`last_verified_at` | 首次发布时间、内容更新时间、最近核验时间 |
| `is_recruitment_open` | 是否符合该赛事的招募开放条件；不表示当前用户已获操作权限或组队功能已上线 |
| `primary_source` | 已核验主来源对象或 `null` |

来源对象统一为 `{id, source_type, source_name, source_url, source_published_on}`。只公开已核验来源，不返回内部核验依据、操作者或下架原因。

### 详情

`GET /api/v1/competitions/<id>/`，无需登录。成功 `200`；不存在、草稿及下架赛事统一返回 `404`，避免暴露非公开内容。

详情包含列表全部字段，并增加：

| 字段 | 含义 |
| --- | --- |
| `description`、`tracks`、`eligibility` | 详情、赛道说明、参赛资格，均为文本 |
| `team_size_min`、`team_size_max` | 人数下限与上限，未知可空 |
| `registration_method`、`registration_url` | 报名说明与外部报名链接 |
| `campus_arrangements` | 校内安排 |
| `campus_deadline`、`campus_deadline_at`、`campus_deadline_timezone` | 校内截止日期、精确时刻、原通知时区 |
| `submission_deadline`、`submission_deadline_at`、`submission_deadline_timezone` | 作品提交截止日期、精确时刻、原通知时区 |
| `deadline_notes` | 截止时间补充说明 |
| `recruitment_deadline` | 平台招募截止时刻，与官方报名截止分别维护 |
| `sources` | 全部已核验来源数组 |

列表与详情均为只读，不执行采集、AI 生成或发信。前端把内容作为文本渲染，外链仅允许 `http` / `https`。

## 本人资料

| 方法与路径 | 请求 | 响应 |
| --- | --- | --- |
| `GET /api/v1/accounts/csrf/` | 无 | `200 {"csrfToken":"..."}`，同时设置 CSRF Cookie |
| `GET /api/v1/accounts/me/` | 登录会话 | `200` 本人资料；匿名为 `403` |
| `PATCH /api/v1/accounts/me/` | 可选 `wechat_id`、`phone_number` | `200` 更新后的本人资料；不允许提交其他字段 |

本人资料字段：

```text
id, public_code, email, wechat_id, phone_number, contact_updated_at,
school_email_verified, has_contact_details, account_eligibility
```

`account_eligibility` 结构为：

```json
{"eligible":false,"reasons":["email_unverified","contact_required"],"restriction_ends_at":null}
```

原因可能为 `login_required`、`account_disabled`、`email_unverified`、`account_restricted`、`contact_required`；本人资料接口本身仅供有效登录用户读取。该结果是新增招募/申请的**账号门槛**，后续业务还须检查赛事、队伍、名额和对象权限。目前没有可执行招募或申请的 HTTP 路由。

本人联系方式不放入公开赛事接口；本人资料响应禁止缓存。提交 `email`、权限或验证状态等额外字段返回 `400`。用户可在业务限制期间读取资料、维护联系方式，不把临时业务限制等同于停用账号。

## 账号认证

下表路径均以 `/api/auth/browser/v1/` 开头。只开放浏览器 Session 模式，不提供 App token。

| 方法与相对路径 | JSON 请求 | 正常流程 |
| --- | --- | --- |
| `POST auth/signup` | `email`, `password` | `200` 注册并建立会话，邮箱仍未验证；不自动发送验证码 |
| `POST auth/login` | `email`, `password` | `200` 登录；未验证账号可以登录 |
| `GET auth/session` | 无 | 已登录 `200`；未登录 `401`，结合 `meta.is_authenticated` 判断 |
| `DELETE auth/session` | 无 | 正常退出返回 `401` 且 `meta.is_authenticated=false` |
| `GET account/email` | 无 | 查看本人 allauth 邮箱记录 |
| `PUT account/email` | `email`：当前绑定邮箱 | `200` 已提交发送；只允许向本人当前、未验证的主邮箱发送或重发 |
| `POST auth/email/verify` | `key`：邮件中的验证码 | `200` 核验成功，随后重新获取本人资料 |
| `POST auth/password/request` | `email` | 进入密码找回流程，正常可返回 `401`，见下文 |
| `POST auth/password/reset` | `key`, `password` | 完成重置后回到未登录状态，正常可返回 `401` |
| `POST account/password/change` | `current_password`, `new_password` | 已登录时修改密码；本轮页面未提供入口 |
| `POST auth/reauthenticate` | `password` | 验证当前密码；本轮页面未提供入口 |

邮箱去首尾空白并转小写，域名必须精确为 `tongji.edu.cn`，类似 `tongji.edu.cn.example.org` 无效。重复邮箱注册不会覆盖原账号、密码或资料。User 与 allauth 邮箱记录在同一注册事务中保存。

验证结果只读取属于当前用户、与 `User.email` 相同且 `primary=true`、`verified=true` 的 allauth `EmailAddress`。未提供邮箱自助换绑；后台也不允许把邮箱手工标记为已验证。历史或管理员创建的账号首次通过网站登录时，只对完全缺失的邮箱记录补建未验证主邮箱，不继承其他地址的验证状态。

### 验证码与限流

| 规则 | 当前实现 |
| --- | --- |
| 学校邮箱验证码 | 6 位数字；在发起流程的同一浏览器会话中提交 |
| 有效期 | 从本轮首次发送起 10 分钟；重发不延长 |
| 重发 | 本轮最多重发 3 次；重发成功后旧码失效 |
| 输入错误 | 最多 5 次；耗尽、过期或成功使用后，本轮不能再用 |
| 发信频率 | 同一邮箱 60 秒内最多 1 次、每小时最多 5 次；同一 IP 每小时最多 20 次 |
| 注册频率 | 同一 IP 每小时最多 5 次 |
| 登录频率 | 同一 IP 每分钟最多 30 次；失败另限制同一键 5 分钟 5 次、同一 IP 5 分钟 20 次 |
| 密码找回 | 验证码 10 分钟、最多 5 次尝试；发信频率与邮箱核验相同；码的格式与邮箱验证码不同，以邮件原文为准 |

限流由服务端执行。前端倒计时只是提示，不是权限依据。开发默认 Console 邮件后端，在终端查看验证码；这不代表真实学校邮箱已收件。SMTP 发送异常返回安全错误，不把服务商响应或凭据暴露给前端。

### 正常的 401

allauth 的 `401` 有时用于表示“目前未登录或正在完成认证流程”，不能统一显示为请求失败。

- 请求找回密码后：检查 `data.flows` 是否包含 `{"id":"password_reset_by_code","is_pending":true}`，满足时展示填写验证码及新密码的表单。
- 重置成功后：确认 `meta.is_authenticated=false`，并且已没有待完成的 `password_reset_by_code`；提示用新密码登录，不假定自动登录。
- 退出后：确认 `meta.is_authenticated=false`，清空页面中的本人资料。
- 未登录读取 Session：识别未登录状态，显示登录/注册入口。

前端实现见 `frontend/src/api/accounts.js` 与 `frontend/src/utils/account.js`；不要仅根据 HTTP 状态认定密码重置完成。

## 错误处理

DRF 业务错误通常为 `{"detail":"..."}` 或字段错误对象；allauth 通常包含 `status`、`errors`、`data`、`meta` 中的相关字段，两者格式不同。CSRF 与安全异常包装另有稳定 `code`，不得把所有响应强行当作同一结构。

| 状态 | 常见含义与处理 |
| --- | --- |
| `400` | 字段、密码、邮箱或验证码错误；显示可理解的提示，保留可修改输入 |
| `401` | 先按上一节识别正常账号流程，其他情形提示重新登录 |
| `403` | 未登录访问本人资料、CSRF 失效、操作无权或本轮重发已达上限；不能全部当作验证码错误 |
| `404` | 赛事不可公开访问、页码无效或路由不存在 |
| `405` | 请求方法未开放，例如自行添加、更换或删除邮箱 |
| `409` | 验证流程已结束/过期、已验证邮箱或注册保存冲突；刷新账号状态后重新开始适当流程 |
| `429` | 请求过于频繁；等待后再试，不自动连续重发 |
| `503` | 发件服务不可用；不宣称验证码已发送，不展示 SMTP 内部错误 |

`GET account/email` 等 allauth 入口不等同于公开邮箱查询；只管理当前会话对应用户。所有真正决定能否发布和申请的检查都应在后端业务入口执行，不能依赖前端按钮。
