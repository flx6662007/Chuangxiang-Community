# 后端代码入口

一个 Django/DRF 服务，按业务拆分应用。运行步骤见[后端开发说明](../docs/backend-development.md)，当前成果见[团队进度](../docs/progress.md)。本页描述仓库代码；目标环境仍需单独配置数据库、导入资料、模型与索引，不能以代码存在判断已部署。

第一次读代码，先按[代码导读](../docs/code-guide.md)走完一次赛事请求，再使用下面的表格查找其他模块。

## 按功能找目录

当前赛事资料主线是人工整理、编审入库和公开版本检索，首次接入见[赛事资料与检索交接](../docs/competition-search-handoff.md)。`competition_catalog/` 同时保留学校 255 项目录、官网登记、原文监测及提取发布能力；`ingestion/` 保留历史采集命令。它们不是网页浏览的前置任务，也不代表目标机器已设置自动采集。

| 目录 | 职责与主要入口 |
| --- | --- |
| `config/` | `settings.py` 读取环境配置，`urls.py` 挂载业务路径 |
| `accounts/` | 用户与限制模型、学校邮箱认证、会话、资料与资格判断；`headless_urls.py` 对接 allauth |
| `competitions/` | 赛事及来源模型；`views.py` 查询，`serializers.py` 控制公开字段，`services.py` 维护发布与变更 |
| `teams/` | 招募、申请、成员、退出和解散；`services.py` 负责权限、状态机与事务，`urls.py` 提供接口 |
| `notifications/` | 站内通知、本人读取与已读操作 |
| `governance/` | 举报、申诉与管理留痕；`services.py` 负责本人权限、去重及独立复核，`admin.py` 提供处理表单 |
| `competition_catalog/` | 学校赛事目录、官网与原文版本；`api_urls.py` 提供目录读取，历史监测、提取与发布工具仍保留 |
| `curation/` | 人工知识正文、来源、版本、审核及发布；管理命令导入赛事/科研资料、建立关联并重建检索索引 |
| `information_library/` | 管理员只读信息库、科研/快讯公共读取及赛事混合检索；`selectors.py` 聚合白名单字段，`public_views.py` 提供公共接口，`competition_search.py` 提供赛事检索；见[信息库说明](../docs/information-library.md) |
| `ai_services/` | 首页聊天、流式回答、多轮理解、赛事向导及公开资料检索；另保留通知提取/快讯草稿服务。两套模型配置独立，见[AI 服务](../docs/ai-services.md) |
| `research/` | 科研资料、来源、版本、结构化事实及导入；公共列表/详情由 `information_library` 提供，受 `PUBLIC_RESEARCH_ENABLED` 控制 |
| `resources/` | 学习资源、分类与赛事/科研关联；已提供公共列表、详情、筛选选项及受权限保护的草稿预览 |
| `newsletters/` | 快讯及其版本、引用模型；公共读取由 `information_library` 提供，完整在线编辑/确认流程仍待接入 |
| `favorites/` | 收藏模型基础，尚未挂载独立公共业务路由 |
| `ingestion/` | 官方网页读取与历史采集适配器、候选和受控采纳；`http.py` 也供当前可选联网搜索复用 |
| `common/` | 共用校验、编码与历史快照规则 |

## 代码约定

- `models.py` 与 `migrations/`：字段、约束和结构演进；迁移必须提交，团队各自执行已有迁移。
- `serializers.py`、`views.py`、`urls.py`：请求参数、公开字段和 HTTP 接口；复杂写入交给服务层。
- `services.py`：权限与业务状态、事务、锁和审计；不要在视图或脚本里直接改状态绕过服务。
- `admin.py`、`templates/admin/`：管理员入口；可审计业务使用专门操作，历史记录只读。
- `tests.py`、`test_*.py`：对应业务的自动化验证，构造数据仅进入测试库。
- `management/commands/`：采集、到期结算和初始化等命令；定时脚本在根目录 `deploy/windows/`。

修改人工赛事正文与发布规则先看 `curation/`；修改历史采集规则再看 `ingestion/` 和 `competition_catalog/`。普通列表与详情读取已保存数据；用户主动发送 AI 问题时才进入模型及可选联网流程。

首页聊天读取 `DEEPSEEK_*`，内部草稿读取 `AI_ENABLED`、`AI_*`，关闭后者不会关闭首页聊天。科研的公共读取与 AI 检索默认关闭，设 `PUBLIC_RESEARCH_ENABLED=1` 并导入已发布资料后才可用。近期接入步骤见[科研交付](../docs/releases/research-ai-20261007.md)和[多轮与联网交付](../docs/ai-optimization-20261008.md)。

`.env`、`.venv/`、`.local/` 属于本机配置、依赖和运行数据，不提交。密钥只在服务端配置，真实数据库记录不通过 GitHub 同步。
