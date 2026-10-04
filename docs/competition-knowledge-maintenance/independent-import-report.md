# 新版赛事知识独立导入验收

日期：2026-10-04。资料版本：`874ccd5c6dddf794`。

新版资料已统一为一条独立导入与检索链路。三个导入 JSON 位于 `imports/`，文档数分别为 65、41、92，共 198 条。生成器默认生成这三个文件，业务赛事与资源依赖均为 0。

## 实现

- `load_competition_knowledge` 在一个事务中完成三包导入、版本保存和审核记录，返回可检索文档数。
- 相同内容再次加载复用现有文档、版本与审核记录；内容变化保存新版本。
- 新版移除的本包文档自动撤下并保留历史；已经撤下的条目维持其状态。
- 资料正文、结构字段、段落证据及版本在导入时一并校验。
- 检索通过 `search_competitions()` 返回正文、匹配理由与来源。聊天接口由队友接入。

## 后端回归

在隔离 PostgreSQL 测试库运行以下测试，**111 项通过，耗时 14.782 秒**，Django 系统检查通过：

```powershell
python backend/manage.py test curation.test_product curation.test_knowledge_delivery curation.test_knowledge_loader information_library.test_competition_search ai_services config --settings=config.postgres_test_settings --keepdb --noinput
```

测试覆盖 198 条完整导入、数据库检索、重复执行、版本更新、撤下、移除记录、三包事务回滚、权限校验和原数据保留。既有聊天与配置测试一同通过。

## 真实模型链路

通过管理命令向隔离测试库导入 198 条知识，使用本地 `BAAI/bge-small-zh-v1.5` 建立 864 段数据库索引，再执行三种检索模式。模型 revision 为 `7999e1d3359715c523056ef9478215996d62a620`。

测试问题：全国大学生电子设计竞赛嵌入式AI专题赛（英特尔杯）。

| 模式 | 实际运行模式 | 返回条数 | 查询耗时 | 正文与证据 |
| --- | --- | --- | --- | --- |
| keyword | keyword | 5 | 0.066 秒 | 完整 |
| semantic | semantic | 5 | 0.065 秒 | 完整 |
| hybrid | hybrid | 5 | 0.067 秒 | 完整 |

三种模式首条均命中英特尔杯。再次执行导入命令，复用 198 条，新增文档、版本审核均为 0。整条验证耗时 15.662 秒；运行环境为 Windows、Python 3.13.13、CPU、本地已准备的 BGE 模型。以上查询耗时来自本次链路检查，150 题方案比较见原评测报告。

详细数据见 [independent-import-report.json](independent-import-report.json)。验证结束后事务回滚，测试库恢复运行前状态；实际业务库保持原状。

## 资料与交付包

`scripts/test-competition-evaluation.py`：17 项通过。`scripts/check-competition-knowledge.py`：255 项处理结论、198 条资料、864 段正文、20 项样本检查通过。

接入包包含统一导入命令及三个独立 JSON，说明、代码和导入数据采用同一目录约定。资料正文版本保持 `874ccd5c6dddf794`。
