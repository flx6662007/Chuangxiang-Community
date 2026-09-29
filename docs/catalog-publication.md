# 赛事提取与上架

学校目录决定收录范围；官网原文、附件和提取结果保存在后台。公开页面只读取已经核验发布的赛事，不在用户打开页面时运行爬虫或生成卡片。

## 处理流程

1. `sync_competition_catalog` 在已核对的官网范围发现通知，优先读取当年报名、参赛说明；保存正文与内容版本。
2. `process_catalog_notices` 从原文提取赛事名称、届次、主办方、资格、赛道、人数、报名方式和各类截止日期。
3. `fetch_catalog_attachments` 读取通知里的 PDF、DOCX 规则，单独保存附件来源和正文；随后再次提取。
4. `publish_extraction` 重新核对原文版本、赛事归属和字段证据，写入正式赛事与目录关联。首页、无关赛事、获奖报道、缺少关键字段或存在冲突的内容留在后台。

无需模型密钥或付费 API。当前使用有版本号的文本提取规则，不能把“找到网页”当作“全部信息已提取”。每项结果都保存字段证据、缺项与处理原因，后续 AI 可读取这些材料，但不能直接改写发布状态。

## 首次运行

在 `backend` 目录安装依赖、迁移并初始化目录：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py init_competition_catalog
.\.venv\Scripts\python.exe manage.py process_catalog_notices --dry-run
```

首次无原文时，先运行 `sync_competition_catalog`。查看预览后，用现有的赛事维护账号执行发布；下方 `123` 仅为示例，替换为本机实际账号编号：

```powershell
.\.venv\Scripts\python.exe manage.py process_catalog_notices --publish --actor-id 123
.\.venv\Scripts\python.exe manage.py fetch_catalog_attachments --limit 40
.\.venv\Scripts\python.exe manage.py process_catalog_notices --publish --actor-id 123
```

命令不会创建账号或授予权限。执行人须启用、具有 staff 标记，以及新增赛事、修改赛事、新增赛事来源的既有权限。可用 `--code 2026143` 只处理一个目录条目；提取命令还支持 `--notice-id` 选择原文。

## 自动运行

在服务端 `.env` 配置已授权的维护身份：

```dotenv
CATALOG_AUTO_PUBLISH=1
CATALOG_PUBLISH_ACTOR_ID=123
```

Windows 已有每 6 小时任务依次执行专用采集、目录监测、正文提取、附件处理、再提取。无需调整周期；使用无窗口 Python，子进程也不创建终端。新电脑按[本机维护说明](maintenance.md)安装任务。关机、退出登录、数据库或网络不可用会影响运行。

新环境默认关闭自动发布；`--scheduled` 读取上述配置，`--publish` 为明确的手动发布操作。AI 配置不参与此流程。

## 发布规则

- 至少明确赛事归属、届次、主办方、参赛资格和一项官方报名或作品截止日期；原文必须仍是该地址的当前版本。
- 报名截止与作品提交截止分开。以报名截止优先判断是否还能报名；已截止的有效记录归入历史，不改成当年开放赛事。
- 抓取日期、网页发布日期不能替代赛事年度。不同组别、不同阶段和延期通知存在歧义时保留待核对，不取最晚日期假装仍开放。
- 未提取到的人数、报名链接等保留为空，页面显示“暂未收录，请查阅原文”，不反推官方没有写；教师人数不当成学生人数，学校目录等级不当成全国级别。
- 新卡片默认关闭站内招募，管理员核对可组队范围、人数及招募期限后再开启。
- 同原文同规则重复执行不会重复创建卡片。新版本与现有赛事有变化、已有人工修订或人工下架时，不自动覆盖或恢复；在后台保留待处理结果。
- 同一赛事另有更新通知时，即使旧通知字段更完整，也阻止旧稿抢先发布；先核对更新稿。
- AIC、NCDA 保留原有专用流程，通用提取跳过这些目录，避免同一个赛项重复上架。

## 后台处理

在 Django Admin 的“官网赛事提取”中查看结论、字段证据、缺项、错误和关联卡片。具备相应权限的管理员可尝试核验发布或拒绝；后台不提供直接编辑候选 JSON 冒充已核验的入口。修正规则后必须升级规则版本再提取，保留旧记录。

附件仅解析授权域名的公开 PDF、DOCX，下载不超过 8 MB；不执行宏或文档内容，不跟踪文档内链接。扫描件、加密文件、旧 DOC 和超限文件保留明确原因；不绕过登录、验证码或网站采集限制。

正文、附件、候选、正式赛事是不同数量。真实运行结果见[团队进度](progress.md)，不能把原文页数或目录条数当作已上架赛事数。
