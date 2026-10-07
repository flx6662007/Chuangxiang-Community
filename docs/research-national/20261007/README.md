# 全国高校科研资料 · 2026-10-07

本包覆盖 24 所高校、128 个实验室／团队，120 条进入导入包，8 条因来源不可读取而暂不导入。实验室介绍与可选招募复用同一条记录。本包不包含同济资料。

## 提交内容

| 文件 | 用途 |
| --- | --- |
| `records.json` | 可维护的数据源，保留官方来源、字段关联和可读性状态，用于重建和追溯 |
| `research-cards.json` | 由数据源生成的 120 条数据库导入记录，也是回归测试的资料夹具 |
| `README.md` | 数据维护约定 |

离线 HTML、Excel、来源索引副本、检查报告和截图属于本机审阅产物，不随代码提交。生成器只维护 `research-cards.json`，检查结果输出到终端。

## 字段与统计

`records.json` 的 `display` 保存展示事实，`fieldLinks` 将研究介绍、成果及招募条件关联到官方页面。空字段不填猜测值；阅读对象不等于申请资格，本科学历不等于本科在读。申请主要跳转官方链接，跨校资格单列。

导入包结构：

- `scope: national`：独立全国批次。
- `laboratories`：每条恰好九个字段：`id/title/unit/summary/participation/evidenceNote/date/verifiedOn/sourceUrl`。
- `profiles[id]`：研究方向、地点、成果、招募字段、招募来源标记及字段链接。
- `sources[id]`：已读取来源的 `url/title/verifiedOn`，用于维护补充来源；主链接不重复建行。

按 2026-10-07 资料计，120 条中有 83 条包含具体招募字段、15 条只有招募入口、22 条为纯实验室介绍；98 条附招募来源，排除 4 条历史批次后招募筛选为 94 条。共 129 个记录内去重来源页面，包含 9 个补充页面；同页不同章节锚点不重复计数。筛选数量会随数据及截止时间变化。

## 维护与生成

修改 `records.json` 的事实和对应来源，确认 `reviewStatus`、来源 `readable`、`checkedOn` 与字段链接后，在仓库根目录执行：

```powershell
backend/.venv/Scripts/python.exe scripts/build-national-research-package.py
backend/.venv/Scripts/python.exe scripts/build-national-research-package.py --check
```

生成器验证稳定编号、实体及主来源重复、官方域名、范围限制、日期及字段链接，只有 `ready_for_review` 且主来源可读的记录进入导入包。构建不会修改数据库或开放科研页面。

后续按[交付说明](../../releases/research-ai-20261007.md)完成数据库预演、应用与索引重建。导入器按稳定编号合并并保留未包含的记录；下架记录保持下架，遇到来源冲突回滚整批。资料／来源更新后需重建科研与资源统一索引。
