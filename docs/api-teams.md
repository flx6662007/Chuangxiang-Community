# 组队接口

所有路径以 `/api/v1/` 开头并保留末尾 `/`。写请求使用现有 Session + CSRF；新增发布和申请还须验证邮箱、填写联系资料且未受限制。公开 JSON 不含联系方式。

## 请求约定

招募字段：`competition_id`、`duration_days`（3/7/14）、`existing_member_count`、`recruitment_quota`、`foundation_requirement`、`weekly_effort`、`collaboration_mode`、`collaboration_goal`（可空）、`expected_duration`（可空）、`current_skills` / `required_roles` / `required_skills` / `campuses`（词条 code 数组）。可选 `team_id` 表示本队新一轮招募。未知字段拒绝。

编辑 PATCH 只提交允许的内容字段与 `expected_version`（看到的卡片版本）；不能改赛事、队伍、有效期。申请 POST 提交 `expected_version`、`weekly_effort`、`desired_roles` / `skills`（code 数组，选填）。角色只能选当前卡片要求的角色。

申请动作提交 `expected_version`（当前卡片版本）、`expected_application_version`（当前申请资料版本）；继续申请额外提交新资料。回应退出/解散请求提交 `response: "agree" | "reject"`；撤回请求传 `{}`；创建退出请求传 `kind: "exit" | "removal"`；解散提交 `confirm: true`。

## 地址

| 方法与路径 | 用途 |
| --- | --- |
| GET `recruitments/options/` | 角色、技能、校区和固定枚举 |
| GET / POST `recruitments/` | 公开分页 / 新建招募 |
| POST `recruitments/preview/` | 同发布参数，校验并返回实际有效期，不落库 |
| GET / PATCH `recruitments/<id>/` | 公开详情 / 招募者编辑 |
| POST `recruitments/<id>/close/` | 招募者关闭，提交 expected_version |
| POST `recruitments/<id>/applications/` | 提交申请 |
| GET `applications/?scope=sent或received` | 本人发出或收到的申请，分页 |
| GET `applications/<id>/` | 当事人申请详情 |
| POST `applications/<id>/<action>/` | accept、reject、withdraw、end、continue、confirm、revoke-confirmation |
| GET `applications/<id>/contact/` | 受权双方查看对方最新联系方式，禁止缓存 |
| GET `teams/mine/` | 本人队伍，分页；包含已结束关系用于追溯 |
| GET `teams/<id>/` | 本队内部详情，非成员无权访问 |
| POST `memberships/<id>/departure-requests/` | 退出/移除 |
| POST `departure-requests/<id>/respond/` 或 `withdraw/` | 回应/撤回 |
| POST `teams/<id>/dissolution-requests/` | 发起解散 |
| POST `dissolution-requests/<id>/respond/` 或 `withdraw/` | 回应/撤回 |
| GET `notifications/` | 本人消息分页，`unread=true` |
| POST `notifications/<id>/read/` | 标记本人消息已读，重复操作返回现状 |

## 响应

列表均为 `{count,next,previous,results}`。招募字段平铺：`id,code,team:{id,code},competition:{id,code,title,edition},version`、模板字段、`joined_member_count,current_existing_member_count,remaining_slots,expires_at,last_edited_at,is_open,status,allowed_actions`。多选读值为 `[{code,name}]`；写入用 code 数组。状态为 `open/full/paused/closed/expired/unavailable`。允许动作是给当前登录用户的提示，每次写操作仍重验。

申请对象包含 `id,recruitment,applicant:{public_code},is_applicant,version,recruitment_version,status,is_paused,changed_fields,end_reason,weekly_effort,desired_roles,skills,applicant_confirmed_at,recruiter_confirmed_at,contact_available,allowed_actions,submitted_at`。`changed_fields` 为该申请已接受版本与最新卡片的差异字段名。联系方式单独返回 `{public_code,email,wechat_id,phone_number,contact_updated_at}`，其他接口不夹带联系资料。

队伍详情包含 `id,code,competition,recruiter:{public_code},is_recruiter,dissolved_at,recruitments,memberships,departure_requests,dissolution_requests,allowed_actions`。成员含 `id,user:{public_code},is_self,is_recruiter,application_id,joined_at,ended_at,end_reason,allowed_actions`；请求含主键、状态、双方/本人标识、创建/截止/回应/结算时间、允许动作。通知含 `id,title,body,created_at,read_at,kind,payload,target:{type,id}`。

动作编码：卡片 `apply/edit/close`；申请为地址表的动作名（联系权限单独读 `contact_available`）；队伍 `publish/dissolve`；成员 `exit/removal`；请求 `respond/withdraw`。编辑表单人数采用 `current_existing_member_count`；`existing_member_count` 是版本当时的申报值，可能因旧轮成员离队高于当前展示值。

卡片还返回 `effective_expires_at` 作为当前实际截止（原卡期限与最新赛事招募截止取早）；`expires_at` 保留首次发布时的期限。赛事截止更正不覆盖历史、不延长原卡。

错误：`{code,detail,fields?}`；400 字段格式不合法，403 账号或动作权限不足，404 对象不存在/不可见，409 版本变化或状态冲突。常见 code：`invalid_fields,account_ineligible,forbidden,stale_version,card_unavailable,already_applied,already_member,team_paused,request_resolved`。冲突后重新获取对象。

公开筛选支持 `search,competition_id,role,skill,campus,collaboration_mode,open_only`，分页 `page,page_size`（默认20，最多50）。多个筛选取交集，过滤在数据库执行。

## 后端服务协作

赛事联动使用 `with teams.services.lock_competition_graph(competition_id):` 获取一致锁，修改赛事后在同一事务调用 `reconcile_competition(competition_id, now=...)`。不要先持有赛事锁再调用此入口。组队锁顺序为用户、赛事、队伍、卡片、申请、成员/请求；PostgreSQL 先用同届事务 advisory lock 稳定发现的对象集合。此实现偏向试点正确性，同届写动作串行。

`python manage.py settle_team_deadlines` 结算到期卡片与固定 24 小时请求。写入口也即时结算；后台任务延迟不延长操作权限。消息已读不会继续申请或确认入队。

`python manage.py seed_recruitment_options` 幂等补充通用角色、技能和校区词表，不重启用已停用项。管理员可在 Django Admin 维护词表；招募业务记录只读，招募列表的“核实下架”通过专门事务服务执行，须填写核实理由并具备 `teams.change_recruitment` 权限。下架只结束未入队申请，保留有效正式成员联系权限。
