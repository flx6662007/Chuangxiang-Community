# 赛事助手交接

本版完成“用户需求 → AI 理解 → 找赛事 → 分析适配 → 找队友”，复用现有招募、申请和双方确认流程。赛事知识统一使用 BGE 混合检索；科研页面显示“暂不开放”，资料独立导入。

## 队长部署步骤

先按 [后端开发](backend-development.md) 配好 Python、PostgreSQL 和 `backend/.env`。以下命令在仓库根目录、项目 Python 环境中执行：

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-retrieval.txt
python backend/manage.py migrate
$actorId = [int](Read-Host '管理员用户 ID')
python backend/manage.py load_competition_knowledge --actor-id $actorId --apply --reason '启用赛事助手资料'
python scripts/prepare-competition-model.py
$env:COMPETITION_EMBEDDING_MODEL_PATH = "$PWD/.local/models/bge-small-zh-v1.5"
$env:COMPETITION_SEMANTIC_INDEX = "$PWD/.local/competition-search/database.npz"
python backend/manage.py rebuild_ai_index
python backend/manage.py runserver
```

在 `backend/.env` 配置 `DEEPSEEK_API_KEY`，模型与服务地址沿用 `.env.example` 的 `DEEPSEEK_*` 项。上述两个索引环境变量也可保存到该文件，供重启后的服务读取。科研保持 `PUBLIC_RESEARCH_ENABLED=0`。模型首次下载后可本地检索；队长在自己的电脑生成索引。

另开终端进入 `frontend`，执行 `npm ci`、`npm run dev`。默认代理后端 8000 端口，配置见 [前端启动](../frontend/README.md)。以上用于本机验收；对外内测按 [部署说明](deployment.md) 启动服务，再配置内网穿透的域名、允许主机、CSRF 来源、HTTPS 与真实邮件服务。

部署后每分钟执行 `python backend/manage.py settle_team_deadlines`，更新截止后的组队目标。Windows 维护脚本的 `settle` 任务使用此命令，设置方法见 [定时任务](maintenance.md)。

## 资料与招募关联

使用 `docs/competition-knowledge-maintenance/imports/` 下的三个现行导入包，统一命令同时导入正文、来源、学习资源并建立组队目标。资料更新后重复运行导入和索引命令。正文版本保留历史，相同内容重复导入复用已有对象；撤下内容停止返回。检索字段与底层调用见 [检索接口](competition-search-handoff.md)。

资料版本 `d744beaf5c993b25`：255 项目录有处理结论，188 项正式收录为 198 篇、912 段，67 项保留内部处理记录。2026-10-06 本地导入得到 188 个组队目标（44 个面向下一届），其中 178 个开放招募，以及 302 条学习资源。资源提供说明、官方外链与赛事关联。

组队规则：

- 报名截止前或截止时间未知，可以提前组队；报名开始日期不限制组队。
- 到达明确截止时刻，或日期型截止日次日零点（北京时间），开放下一届组队；已确认结束的比赛同样处理。
- 下一届显示“下一届（官方届次未公布）”。原资料保留原届次，下一届规则随新通知更新；原队伍仍属于原届次。
- 个人赛保留个人参赛形式。平台允许组队与官方是否正在报名分别判断。

助手按角色、每周投入和协作方式筛选开放且有名额的目标届次招募，按技能排序，排除本人的招募和已加入的赛事。结果提供该届招募列表与发布入口；申请继续执行账号核验、联系方式及双方确认流程。

## 接口与修改入口

`GET /api/v1/ai/guide/` 恢复会话；`POST /api/v1/ai/guide/` 执行操作，使用 Session + CSRF，游客可查询。会话保留 7 天，登录身份变化后重新开始。

```json
{"action":"search","message":"我是大二学生，会Python，每周5小时，想找软件类比赛"}
```

后续操作为 `analyze`、`teammates`（携带 `record_id`），`retry` 重试当前问题，`reset` 清空条件。`profile` 支持学历、年级、专业、兴趣、技能、每周时间、人数、协作方式和角色；`filters` 使用固定检索字段，另支持 `recruitment_open`。

结果包括 `candidates`、`selected`、`recruitments`、`team_context`、`answer`、资料版本和参考日期。字段判断区分满足、不满足、信息不足；明确不满足的候选排除。模型负责组织解释和准备建议，匹配状态由规则计算。

`answer.mode` 为 `model` 或 `rules`，每段包含 `text`、`evidence_ids` 和服务端解析的 `citations`。调用失败时保留检索结果并提供重试。刷新会话复用内容一致的回答，不调用模型；生成后重新检查资料、目标与队伍状态。请求只传用户明确填写的条件、公开事实和招募条件。

| 要修改的部分 | 文件 |
| --- | --- |
| 需求理解、条件和队友匹配 | `backend/ai_services/guide.py` |
| AI 回答与引用校验 | `backend/ai_services/guide_answer.py` |
| HTTP 与会话 | `backend/ai_services/guide_views.py` |
| 统一检索与聊天适配 | `backend/information_library/competition_search.py`、`backend/ai_services/competition_knowledge.py` |
| 组队时间规则与导入关联 | `backend/competitions/recruitment_policy.py`、`backend/curation/activation.py` |
| 助手界面与请求 | `frontend/src/components/CompetitionGuide.vue`、`frontend/src/api/guide.js` |

## 科研独立维护

公开科研列表、检索和问答默认关闭。原站内 6 条完整内容保存在 `docs/undergraduate-research/site-before-pause.json`，其编号均在已有 90 条资料包中。

```powershell
python backend/manage.py import_research_materials --source docs/undergraduate-research/tongji-20261003-verified/科研卡片候选.json
# 检查结果后，追加 --apply 写入；恢复原 6 条时改用 site-before-pause.json
```

命令只更新 `backend/information_library/data/editorial.json` 的科研内容，保留快讯；重复执行内容不变，不触发赛事导入。导入不开放展示。未来开放时设置 `PUBLIC_RESEARCH_ENABLED=1`、重启后端，并恢复首页科研摘要展示。

## 验证与接续检查

```powershell
python backend/manage.py test competitions resources teams ai_services curation information_library competition_catalog.test_api accounts --settings=config.postgres_test_settings --keepdb --noinput
python backend/manage.py makemigrations --check --dry-run --settings=config.test_settings
python scripts/check-competition-knowledge.py
python scripts/check-knowledge-rebuild.py
python scripts/build-competition-evaluation.py --check
# 在 frontend 目录执行 npm test 和 npm run build
```

2026-10-06 本地验证：后端完整回归 493 项中 490 通过、3 跳过；最后调整回答上下文后，`ai_services.test_guide ai_services.test_guide_answer curation.test_research_import information_library` 专项 102 项通过。前端 58 项及构建通过；迁移、资料一致性、重复导入与重建已验证。

固定 150 题评测：混合检索开发集 Hit@5 为 98.89%，冻结集为 100%，硬条件违规均为 0；纯语义冻结集为 80%。题目、命令和逐题结果见 [评测说明](competition-evaluation/README.md)。

真实 DeepSeek 与浏览器已验证条件提取、赛事分析、来源、会话恢复、下一届找队友空结果及发布入口。隔离数据库覆盖查到招募、申请、接受和双方确认；本地预览库未建立真实队伍。引用与数字检查已实现，内测继续抽查模型表述是否与原文一致。

队长环境验收：检查本届与下一届标签、资源中心关联、科研关闭；用真实账号完成邮箱验证、发布招募、申请和双方确认，再检查公网访问。部署需要自己的数据库、密钥、模型与索引，本机数据和运行日志不随代码交付。
