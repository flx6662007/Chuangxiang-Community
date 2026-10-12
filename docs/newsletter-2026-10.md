# 2026年10月创享快讯维护与发布

本期标题为“创享快讯 · 2026年10月”，原文日期为2026年10月10日。导入包只含2项赛事和5组资源（6个独立资源入口），不包含项目招募、联系方式或原始 Word 附件。公开署名为创享编辑部，不展示个人编辑姓名。

## 数据与代码

- 审查源：`backend/newsletters/data/2026-10.json`。这是经整理的公开资料包，不是在线接口直接读取的配置，也不会自动发布。
- 使用已有 `Newsletter`、`NewsletterRevision`、`NewsletterItem`，不新增业务表。
- 迁移 `newsletters.0003` 仅增加三个可空／可留空字段：版本的 `source_published_on`、`credits`，条目的 `group_title`。旧数据无需回填，原有字段含义不变。
- 迁移 `newsletters.0004` 定向更新已发布的本期快讯编号、标题和公开署名，不改变首次发布时间、原文日期或条目快照。已确认版本不能通过日常编辑直接改写；此迁移只做一次匿名化修正，回滚不会恢复旧署名。
- 本期详情地址随编号改变；旧地址不做重定向，原有外部分享链接需要更新。
- `published_at` 始终是实际站内首次发布时间。原文日期独立保存；不将导入、审核时间称为原文日期或来源核验时间。
- 每个资源仍单独关联 `Resource`。`template-next-cross` 与 `shadcn/ui` 的当期分组标题相同，详情中合并为一组，分别提供链接。
- 首次导入创建缺失的引用草稿；已公开记录按来源、名称及赛事届次匹配复用，不修改其正文、分类、版本或核验时间。多个候选、来源不一致、撤下／不可用对象都会阻止导入，整笔事务回滚。赛事同一官网的不同届次不会合并。
- 稳定编码相同、标题与正文完全一致的引用草稿可继续发布；其他流程的草稿须由其原维护流程先发布。不会自动重新公开撤下记录。
- 新建赛事使用现有“直接发布”服务，不冒充整条来源已完成全面核验，不自动开启组队。快讯的人工选题独立于信息中心学校赛事目录筛选，不改变原有目录绑定。
- `--write --publish` 会公开本期以及本包创建／精确匹配的关联草稿资源、赛事；资源也会进入已有资源中心。已有公开对象只复用。
- 草稿建立后，若已公开引用被其他流程改动，发布会拒绝并要求复核，不能把旧正文重新标为新版本。
- 已公开版本不可覆盖。重复导入相同包不新增记录、不重置首次发布时间；不同内容或已存在后续版本会报错，须另建版本更正。

## 公开读取边界

- 列表：`GET /api/v1/editorial/newsletters/`，保留分页、标题和正文搜索。卡片摘要最多180字，站内详情入口为 `detailUrl`，数据库快讯的 `sourceUrl` 留空。
- 详情：`GET /api/v1/editorial/newsletters/<code>/`。本期前端路径 `/newsletters/newsletter-2026-10`。
- 只读取已发布快讯指向的、属于本期的已确认版本。草稿、撤下快讯、错误版本归属返回404；不返回审核人、内部备注或联系人字段，自由文本沿用公共隐私清理。
- 正文使用当期快照。引用仍公开但版本更新时保留原文并标记 `sourceChanged`；来源地址改变时关闭旧链接。引用撤下、转草稿、资源不可用时隐藏整个条目，并隐藏可能残留其内容的导读。全部条目隐藏时列表不显示该期，已知详情地址保留通用空态。
- SPA 来源链接保留 hash 路由；协议、主机、凭据、敏感查询参数（含 hash 内查询）均检查。纯文本正文不执行 HTML。
- 公开阅读已与 AI 聚合解耦。`information_library.selectors`、AI 检索和索引校验没有放宽，含资源快照的整期不会因此自动进入 AI 检索。
- 旧 `editorial.json` 人工摘要兼容入口仍保留；不要为同一期同时建立 JSON 副本。

## 来源核验记录

核验日：2026年10月11日。以下是实际观察的范围；页面可访问不表示已验证所有历史、许可、安全性或服务承诺。

| 条目 | 已核对内容及处理 | 来源 |
| --- | --- | --- |
| APMCM | 阅读官网报名通知及其通知图片，确认第十六届、11月25日报名截止、11月26日06:00至30日09:00比赛、1—3人、允许跨校、至多一名指导教师及英文论文。官网导航仍指向旧赛季；正文来源使用当期通知，报名地址采用图片中的 apmcm26，不猜测旧链接的年份。 | [当期通知](https://www.apmcm.org/detail/2512) · [官方通知图片](https://files.apmcm.org/uploads/images/20260915/1789456047535603.png) |
| 华为 ICT | 确认为2026—2027第十一届。高校官方通知列出实践赛10月31日、创新赛11月30日，太原理工通知另列编程赛11月30日。修正原稿把11月30日作为统一截止日的表述。保留主办方中国区入口；动态报名页面尚未完整核验，不使用其他学校的校内报名日期。 | [大连理工通知](https://chuangxin.dlut.edu.cn/info/1020/16867.htm) · [太原理工通知](https://cxcy.tyut.edu.cn/info/1026/8153.htm) · [华为中国区入口](https://e.huawei.com/cn/talent/ict-academy/#/ict-contest?compId=85132018) |
| 国家级B类 | 检索找到的是其他高校的校内认定，不能作为本站统一分级的依据，去掉统一分级断言。 | [西北农林科技大学通知，明确称“我校认定”](https://xkjszx.nwafu.edu.cn/sstz/7dea170e0cf84a7fa52fd962888aba8b.htm) |
| 国创计划 | 教育部通知确认原稿平台地址的身份。本次直接访问超时，正文标注当前可用性及申报安排未确认，资源 `last_verified_at` 留空。未将“全国大学生创新年会”替换为国创计划平台。 | [教育部通知](https://www.moe.gov.cn/s78/A08/tongzhi/202310/t20231016_1085885.html) |
| GitHub Student Developer Pack | 官方页面可读取，保留学生开发者套件及申请入口；未核实“价值1000+”的币种、范围与条件，删除该数字。 | [官方入口](https://education.github.com/pack) |
| 通用开源模板 | 原稿 `dec0dOS/awesome-project-template` 实际返回 HTTP 404。找到同作者的可访问 `amazing-github-template`，作为明确标注的替代参考；没有声称它是原仓库更名。正式发布前重点审查这项替换。 | [替代参考仓库](https://github.com/dec0dOS/amazing-github-template) |
| Web／全栈模板 | 修复粘连链接；两个独立仓库均可读取。明确 shadcn/ui 是组件资源，并非完整全栈模板。 | [template-next-cross](https://github.com/makeonteam/template-next-cross) · [shadcn/ui](https://github.com/shadcn-ui/ui) |
| Ollama | 官方仓库可读取，保留本地模型运行工具说明，不承诺任意设备可运行任意模型。 | [官方仓库](https://github.com/ollama/ollama) |

## 导入与发布步骤

以下命令由维护者在确认目标环境、代码已部署且已审查资料包后执行；本期原始导入已在本地开发库完成，本次匿名化迁移也仅在本地开发库执行，未写入正式环境或部署。Windows 可将 `python` 替换为 `.venv\Scripts\python.exe`，macOS/Linux 使用项目虚拟环境 Python。

在 `backend/` 中：

```bash
# 与数据库负责人对齐迁移，先查看计划，再应用已有迁移。
python manage.py migrate --plan
python manage.py migrate

# 默认仅查询和预览，不执行 INSERT/UPDATE。
python manage.py import_newsletter

# 保存草稿，不公开；将 123 替换为实际管理员用户 ID。
python manage.py import_newsletter --write --actor-id 123

# 审查后明确发布；同时公开本包对应的关联草稿。
python manage.py import_newsletter --write --publish --actor-id 123

# 再次预览，确认 status 为 published、条目均 reuse。
python manage.py import_newsletter
```

权限：管理员须启用且为 staff，具备快讯主表、版本、内容项的新增／修改权限；创建和发布缺失引用时还需要现有赛事及来源的新增／修改、资源新增／修改权限；新建分类还需对应分类新增权限。可使用已有超级管理员，不应为导入硬编码或创建生产账号。

若匹配多条、已有来源不一致或遇到其他流程草稿，按提示先消歧／审核；不要删记录、强制覆盖或重新创建绕过限制。迁移、代码部署和数据发布是三个独立步骤。

发布后检查发现页入口、原文与站内日期、2条赛事／5组资源、Web组两个入口、署名及手机布局。截止日期和动态官网仍应在实际投稿前再核对。

## 验证

```bash
# 仓库根目录，隔离内存 SQLite，执行真实迁移。
backend/.venv/bin/python backend/manage.py test newsletters information_library resources --settings=config.test_settings --noinput
backend/.venv/bin/python backend/manage.py makemigrations --check --dry-run --settings=config.test_settings
# frontend/ 内，有 Node/npm 的团队环境
npm run build
npm test
git diff --check
```

新增测试覆盖只读预览、草稿隔离、确认版本归属、8条内容／5组资源、两种日期、撤下隐藏、快照更新提示、不安全链接、重复导入、复用对象不变、权限与事务回滚、正文搜索及 AI 边界。并使用实际内存后端和浏览器验证页面。

## 本次交付文件与结果

| 文件（相对仓库根目录） | 修改原因 |
| --- | --- |
| `backend/newsletters/models.py`、`migrations/0003_newsletteritem_group_title_and_more.py`（位于同目录） | 补充原文日期、公开署名与条目分组，共3个字段，无新增表 |
| `backend/newsletters/data/2026-10.json` | 本期经核验整理的公开资料包，排除项目招募 |
| `backend/newsletters/importer.py`、`services.py`、`management/commands/import_newsletter.py`（位于同模块） | 只读预览、幂等导入、权限、事务、确认发布及引用变化检查 |
| `backend/newsletters/presentation.py` | 读取当期公开快照、分组资源、来源变化提示和发布边界 |
| `backend/information_library/public_selectors.py`、`public_views.py`、`public_urls.py` | 接入快讯列表和详情，保留正文搜索，停止用单条来源替代整期入口 |
| `backend/newsletters/tests.py`、`backend/information_library/test_public_api.py` | 新增导入／详情回归测试，更新引用变化后的快照展示预期 |
| `frontend/src/views/NewsletterDetailView.vue`、`WelcomeView.vue` | 新增详情与各加载状态，发现页链接到整期内容 |
| `frontend/src/api/editorial.js`、`frontend/src/router/index.js` | 新增详情请求和站内路由 |
| `frontend/src/layouts/AppLayout.vue`、`frontend/src/styles/home.css` | 保持栏目导航、主题样式及移动端卡片布局 |
| `agent.md`、`docs/README.md`、`docs/api.md`、`docs/database-fields.md`、`docs/frontend-implementation.md`、`docs/information-library.md`、本文 | 同步维护约定、接口、数据库与发布步骤 |

最终验证：后端119项测试、前端78项测试通过，Vite生产构建通过，`makemigrations --check --dry-run` 无缺失迁移，`git diff --check` 无问题。

本机没有 `npm` 命令，前端实际使用内置 Node 执行 `node_modules/vite/bin/vite.js build` 和 `node --test tests/*.test.js`，与 package.json 中对应脚本一致。浏览器使用已安装 Chrome 的临时会话，访问仅绑定127.0.0.1的 Vite 和内存 SQLite 后端，完成发现页至详情、内容数量、署名、375px手机／桌面／横屏、深浅色、栏目锚点、404、错误重试与空态检查，无页面脚本错误。没有运行生产环境迁移、导入或部署；尚未在真实 PostgreSQL 环境验证并发锁行为。
