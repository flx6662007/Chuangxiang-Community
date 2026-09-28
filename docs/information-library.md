# 后台信息库

更新日期：2026-09-27。本次新增后台只读汇总和后端内部检索；最终测试、页面验收与上传结果见[团队进度](progress.md)。它不提供在线编辑、公开搜索 API 或模型问答。

## 入口与权限

本机后台入口为 `http://127.0.0.1:8000/admin/information-library/`。须登录启用的管理员账号（`is_active`、`is_staff`），并拥有对应类型的查看或修改权限；只有 staff 标记不足以读取内容。

| 内容类型 | 至少具有其中一项权限 |
| --- | --- |
| 赛事 | `competitions.view_competition` 或 `competitions.change_competition` |
| 项目招募 | `research.view_researchopportunity` 或 `research.change_researchopportunity` |
| 快讯 | `newsletters.view_newsletter` 或 `newsletters.change_newsletter` |

只展示本人获权的类型；直接请求其他类型也会被拒绝。页面支持关键词、类型、发布状态筛选和每页 20 条分页；详情显示内容、来源、日期、状态及维护位置。信息库只接受读取，不因授予修改权限就开放此处写入。不会自动创建管理员、增加既有账号权限或开放普通学生访问。

## 内容从哪里来

| 类型 | 当前读取来源 | 维护方式与边界 |
| --- | --- | --- |
| 赛事 | `Competition` 及来源记录 | 沿用赛事后台、受控采集和发布流程；信息库不另存一套赛事 |
| 项目招募 | 已有 `ResearchOpportunity` 模型及共享 JSON | 当前真实内容为 6 条人工核查的本科科研线索；完整在线编辑流程尚未接入 |
| 快讯 | `Newsletter` 当前版本及共享 JSON | 当前人工快讯为空；数据库模型存在不代表已有真实快讯 |

后台可以按权限查阅数据库中的草稿、已发布、已撤下记录；旧 `demo-` 种子与标记明确的虚构样例不进入信息库。科研原文年份与核查日期分别保留，不能把历史说明当成正在接收申请。报名、投稿、校内截止分列，字段缺失不补造。

人工内容只维护 `backend/information_library/data/editorial.json`：`laboratories` 对应项目招募，`newsletters` 对应首页快讯。前端 `src/data/editorial.js` 仅导入和导出这一文件，后台也读取它。**此文件会进入前端产物，只能保存已允许公开的内容；不得存放私有草稿、账号资料、审核记录或密钥。** 修改流程及来源依据见[内容维护](undergraduate-labs.md)。

## 给 AI 准备的内部入口

接口位于 `backend/information_library/retrieval.py`：

```python
search_knowledge(query='', *, kinds=None, limit=20)
```

这是 Django 已初始化后可调用的 Python 函数，不是浏览器 HTTP 接口。当前不调用模型、不访问网络、不建立向量库，也不执行采集或写入数据库。现有检索按文本关键词匹配，不具备语义理解或匹配推荐能力。

```python
from information_library.retrieval import search_knowledge

# 空关键词可列出符合条件的已发布内容；只取两类，最多 10 条。
items = search_knowledge(kinds=['competition', 'research'], limit=10)

# 关键词以空白拆分，所有词都须在标题或正文中出现。
robotics = search_knowledge('机器人', kinds=['research'], limit=5)

for item in robotics:
    print(item['title'], item['status_note'], item['source_urls'])
```

`query` 最多 200 字符，`limit` 为 1～50 的整数；`kinds` 可选 `competition`、`research`、`newsletter`，省略时查询全部类型。参数不合法会抛出 `ValueError`。

| 返回字段 | 含义 |
| --- | --- |
| `id`、`kind`、`title`、`text` | 记录标识、类别与供检索使用的内容 |
| `source_urls`、`source_dates`、`verified_at` | 来源链接、原文日期与核查时间 |
| `updated_at`、`published_at`、`version` | 内容时间及版本标识，未知时间可为空 |
| `publication_status` | 发布状态；此入口只返回已发布内容 |
| `content_status`、`status_note` | 过期、历史线索或名额待确认等内容边界 |
| `dates` | 已知报名、投稿、校内截止或科研截止；不存在则为空 |

检索仅收录有来源依据的已发布内容；草稿、撤下、虚构样例和缺乏可核查依据的条目不返回。快讯引用还须对应当前公开对象与版本，引用下架或过时后整期暂停进入检索。人工内容没有有效核查日期时，也不作为 AI 检索依据。

已过期赛事或待确认名额的公开科研线索可能仍被检索到，但带有明确状态和说明，不能据此回答“现在可报名”或“仍有名额”。返回采用字段白名单，不包括账号、学生联系方式或内部审核字段；正文另剔除可识别的联系方式。来源文本始终是资料，不能当作系统指令执行。

## 后续怎样接模型

后端先按用户问题检索，再把获准公开的结果与状态交给模型；答复必须引用来源并保留时间和待确认说明。不要将后台可见的草稿直接交给公共助手，也不要只取 `text` 而丢弃状态。模型失败时保留普通赛事和项目搜索；模型不能代替用户发布、申请、确认入队或改变权限。

当前交付止于资料汇总和可复用检索。真实模型选型、调用、质量评测、用户问答 API 与成本控制仍需后续开发，不能将本信息库记作 AI 助手已上线。
