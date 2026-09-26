# 举报与申诉接口

更新日期：2026-09-26。根路径 `/api/v1/governance/`，路径末尾保留 `/`。浏览器使用已有 Session 与 CSRF；写入请求须携带 `X-CSRFToken`。

## 权限与边界

- 全部入口要求当前登录，不要求邮箱核验或联系方式。仅限制新增招募、申请的用户仍可举报和申诉。
- 每人只能查询本人提交记录和本人可申诉对象；知道他人 ID 不授予访问权。公开赛事或招募页不展示举报内容、举报人及处理人员资料。
- 举报对象仅为赛事和招募；不提供搜索或举报任意用户的入口。非公开对象仅允许已有相应组队、申请或本人招募关系的人提交。
- 同一人对同一对象同时只允许一条待处理记录。举报每分钟最多 3 条、滚动 24 小时最多 10 条；申诉分别为 2 条和 5 条。数据库用户行锁与唯一约束共同防止并发绕过。
- 说明为 1～1000 字符，不上传附件。不要填写无关人员联系方式、密码或验证码。正文按普通文字显示。
- 举报不会自动下架内容、限制账号。申诉成立仅记录独立复核结论，**不自动解除限制、恢复招募或覆盖原处理记录**；实际操作须由相应权限的管理员另外执行并留痕。
- 本版在“我的举报与申诉”读取处理反馈，不发送外部消息，不自动添加站内组队通知。

## 路由

| 方法与路径 | 作用 |
| --- | --- |
| `GET options/` | 获取举报理由、举报状态和申诉状态词表 |
| `GET reports/` | 本人举报列表；支持 `status` 筛选 |
| `POST reports/` | 提交举报 |
| `GET reports/{id}/` | 本人举报详情 |
| `GET appeals/` | 本人申诉列表；支持 `status` 筛选 |
| `POST appeals/` | 提交申诉 |
| `GET appeals/{id}/` | 本人申诉详情 |
| `GET appeal-targets/` | 本人可申诉对象，包括已有待处理申诉的对象 |

三个列表均采用 `count/next/previous/results` 分页，默认每页 20 条，支持 `page`、`page_size`，最大 50 条。提交成功返回 `201` 和完整记录；不提供编辑、删除或撤回历史的接口。

## 提交参数

举报示例：

```json
{
  "target_type": "competition",
  "target_id": 1,
  "reason": "false_information",
  "description": "页面截止日期与列出的官方通知不一致，请核对。"
}
```

`target_type` 为 `competition` 或 `recruitment`。`reason` 可选：

| code | 名称 |
| --- | --- |
| `false_information` | 信息不实或过期 |
| `fraud` | 涉嫌诈骗或不当收费 |
| `inappropriate` | 内容不当 |
| `other` | 其他问题 |

申诉示例：

```json
{
  "target_type": "restriction",
  "target_id": 1,
  "description": "请由另一名管理员复核此项限制的事实依据。"
}
```

申诉对象从 `appeal-targets/` 选择，不让用户猜测编号：

| target_type | target_id 对应记录 | 可提交人 |
| --- | --- | --- |
| `restriction` | `UserRestriction.id` | 被限制本人；历史到期记录也可请求复核 |
| `recruitment_action` | 招募下架的 `AdminAction.id` | 该招募的招募者；不是招募卡 ID |
| `report` | 已处理 `Report.id` | 该举报的提交人；待处理举报不能提前申诉 |

不支持对申诉结论再创建嵌套申诉。上述两类提交均拒绝额外字段，提交人和状态只能由后端确定。

## 响应字段

词表返回 `{ "report_reasons": [{"code":"other","name":"其他问题"}], "report_statuses": [...], "appeal_statuses": [...] }`，各列表均为 `code/name` 对象。

举报、申诉记录公共字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 当前举报或申诉记录 ID |
| `target_type`, `target_id` | 对象类型及编号 |
| `target_title` | 提交时的对象名称快照 |
| `description` | 本人的原始说明 |
| `status`, `status_label` | 当前处理状态及中文名称 |
| `feedback` | 管理员向本人提供的反馈；待处理为空串 |
| `created_at`, `reviewed_at` | 带时区时间；未处理时 `reviewed_at=null` |
| `allowed_actions` | 当前允许动作数组 |
| `effect_note` | 核实结论与实际处罚／撤销的区别说明 |

举报另外返回 `reason/reason_label`。只有已处理且没有待处理申诉的举报返回 `allowed_actions:["appeal"]`；其余记录返回空数组。没有处理人账号、联系方式或他人记录字段。

举报状态为 `pending`（待核实）、`confirmed`（问题已确认）、`dismissed`（未确认违规）。申诉状态为 `pending`（待复核）、`upheld`（申诉成立）、`rejected`（申诉未获支持）。处理完成后不可覆盖结论。

`appeal-targets/` 每项返回：

```json
{
  "target_type": "restriction",
  "target_id": 1,
  "title": "账号新增发布和申请限制",
  "reason": "原限制记录中的理由",
  "occurred_at": "2026-09-26T10:00:00+08:00",
  "can_appeal": false,
  "pending_appeal_id": 2
}
```

没有待处理申诉时 `can_appeal=true`、`pending_appeal_id=null`。这个标记只表示记录资格，提交仍会检查登录、实时重复记录及频率限制。

## 错误与后台处理

| HTTP | 常见 code | 含义 |
| --- | --- | --- |
| `400` | `invalid_fields` | 类型、说明长度、枚举、额外字段或筛选值错误 |
| `403` | `permission_denied`／`login_required` | 未登录、CSRF 失败或无处理权限 |
| `404` | `not_found` | 对象不存在或不属于本人可访问范围；不区分两者 |
| `409` | `duplicate_pending` | 同一对象已有待处理举报或申诉 |
| `429` | `rate_limited` | 每分钟或滚动 24 小时提交次数达到上限 |

业务错误结构为 `{ "code": "duplicate_pending", "detail": "这个对象已有待处理举报……" }`；字段错误可能另外带 `fields`。认证和 CSRF 使用 DRF 原有错误结构。

后台的“举报”“申诉”列表有“核实并反馈”入口，选择结论并填写 1～1000 字反馈。处理需要启用的 staff 账号及对应 `governance.change_report` 或 `governance.change_appeal` 权限；查阅须对应 view 权限。普通网站接口不提供管理员处理方法。

申诉复核者不得是原限制创建人、原下架操作人或原举报处理人，也不得是申诉提交人；超级管理员也不能绕过该回避规则。后台不能新增伪造举报、修改提交正文、删除历史或覆盖已处理结论。新账号或权限授权由负责人另行批准，迁移与启动不会创建管理账号。

## 数据与复现

新增 `governance/0004` 迁移，建立 `Report` 与 `Appeal`，保留既有 `AdminAction`、`UserRestriction` 及组队模型。拉取后按开发说明执行 `python manage.py migrate`。

运行 `python manage.py test governance` 可复现接口、CSRF、不可变历史、管理员回避、数据库约束及 PostgreSQL 并发提交测试。测试使用 Django 独立测试库，不需要真实邮箱或外部服务；SQLite 不执行 PostgreSQL 行锁场景。
