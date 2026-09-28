# 后端代码入口

一个 Django 服务，按业务拆分应用。运行步骤见[后端开发说明](../docs/backend-development.md)，当前成果见[团队进度](../docs/progress.md)。

第一次读代码，先按[代码导读](../docs/code-guide.md)走完一次赛事请求，再使用下面的表格查找其他模块。

## 按功能找目录

新增 `competition_catalog/`：学校 255 项目录、官网白名单、原文版本、运行记录和公开赛事关联。首次运行先迁移，再执行 `init_competition_catalog`；采集结果见[覆盖表](../docs/competition-catalog-coverage.md)。

| 目录 | 职责与主要入口 |
| --- | --- |
| `config/` | `settings.py` 读取环境配置，`urls.py` 挂载业务路径 |
| `accounts/` | 用户与限制模型、学校邮箱认证、会话、资料与资格判断；`headless_urls.py` 对接 allauth |
| `competitions/` | 赛事及来源模型；`views.py` 查询，`serializers.py` 控制公开字段，`services.py` 维护发布与变更 |
| `teams/` | 招募、申请、成员、退出和解散；`services.py` 负责权限、状态机与事务，`urls.py` 提供接口 |
| `notifications/` | 站内通知、本人读取与已读操作 |
| `governance/` | 举报、申诉与管理留痕；`services.py` 负责本人权限、去重及独立复核，`admin.py` 提供处理表单 |
| `ingestion/` | `http.py` 获取官网；`adapters.py` 注册来源并解析 AIC/数维杯；`ncda.py` 解析设计赛表格；`services.py` 保存版本、候选和受控采纳 |
| `information_library/` | 管理员统一只读信息库；`selectors.py` 聚合白名单字段，`retrieval.py` 提供内部检索，`data/editorial.json` 维护前后台共享的公共人工内容；见[信息库说明](../docs/information-library.md) |
| `ai_services/` | 模型调用、提示词、校验与异常；默认关闭，不在浏览请求中调用 |
| `research/`、`newsletters/`、`resources/`、`favorites/` | 已有模型基础，尚未开放完整公共业务接口；科研与快讯公共人工内容由共享 JSON 维护，尚无在线编辑后台 |
| `common/` | 共用校验、编码与历史快照规则 |

## 代码约定

- `models.py` 与 `migrations/`：字段、约束和结构演进；迁移必须提交，团队各自执行已有迁移。
- `serializers.py`、`views.py`、`urls.py`：请求参数、公开字段和 HTTP 接口；复杂写入交给服务层。
- `services.py`：权限与业务状态、事务、锁和审计；不要在视图或脚本里直接改状态绕过服务。
- `admin.py`、`templates/admin/`：管理员入口；可审计业务使用专门操作，历史记录只读。
- `tests.py`、`test_*.py`：对应业务的自动化验证，构造数据仅进入测试库。
- `management/commands/`：采集、到期结算和初始化等命令；定时脚本在根目录 `deploy/windows/`。

需要改赛事内容提取时，从 `ingestion` 开始；需要改卡片外观时修改前端；需要改数据库字段时修改模型并生成迁移。网页读取已经保存的数据，不等待采集或 AI。

`.env`、`.venv/`、`.local/` 属于本机配置、依赖和运行数据，不提交。密钥只在服务端配置，真实数据库记录不通过 GitHub 同步。
