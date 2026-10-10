# 文档导航

先看[当前进度](progress.md)；首次接手代码看[代码导读](code-guide.md)。本目录同时保存运行说明与有来源的资料包，历史方案和单次验收集中在 [archive/](archive/README.md)。

## 开发与运行

| 内容 | 文档 |
| --- | --- |
| 项目总览与本地启动 | [根 README](../README.md) |
| 后端环境、数据库与测试 | [后端开发](backend-development.md) · [后端模块](../backend/README.md) · [模块分工](code-guide.md#模块分工) |
| 前端页面、配置与测试 | [前端说明](../frontend/README.md) |
| 临时网址与内测账号 | [邀请内测](private-beta.md) |
| Windows 解压运行的评审演示包 | [评审包使用与构建](portable-review.md) |
| 服务器部署与费用 | [部署](deployment.md) · [采购清单](procurement.md) |
| 维护命令与人工验收 | [定时任务](maintenance.md) · [操作检查](manual-checks.md) |
| 本轮工程整理 | [整理范围与验证](engineering-cleanup-20261008.md) |

## AI 与信息库

| 内容 | 文档 |
| --- | --- |
| AI 当前接口、检索与配置 | [V3 接入](ai-v3.md) |
| 多轮问答、流式交互与联网搜索 | [10 月 8 日更新](ai-optimization-20261008.md) |
| 赛事推荐、分析与找队友 | [赛事助手交接](ai-assistant-handoff.md) |
| BGE 赛事索引与资料维护 | [检索交接](competition-search-handoff.md) |
| 学习资料问法与检索回归 | [资源评测](resource-evaluation/README.md) |
| 学习资料检索修复与实测 | [10 月 10 日更新](releases/resource-retrieval-20261010.md) |
| 既有 BGE/科研接入步骤 | [V2 接入记录](ai-v2.md)，结合后续更新阅读 |
| 模型调用与内部草稿服务 | [AI 服务](ai-services.md) |
| 后台信息库与公共接口分工 | [信息库](information-library.md) |

## 接口与数据结构

| 内容 | 文档 |
| --- | --- |
| 账号、赛事及聊天入口 | [API 总览](api.md) |
| 资料、目录、资源与 AI 检索 | [资料库接口](api-library.md) |
| 招募与成员流程 | [组队 API](api-teams.md) |
| 举报、申诉与处理 | [治理 API](api-governance.md) |
| 模型与约束 | [数据库字段](database-fields.md) · [用户字段](user-fields-table.md) · [赛事字段](competition-fields-table.md) · [其他字段](remaining-fields-table.md) |
| 原模型交付与初始化 | [数据库交接](database-handoff.md)，阶段状态按历史理解 |

## 资料维护

当前主线是人工整理、导入、关联资源和重建索引。资料源、原包、快照、清单及正式交付物保留原路径。

| 内容 | 文档或目录 |
| --- | --- |
| 现行赛事知识导入 | [检索维护](competition-search-handoff.md) · [资料维护标准](competition-knowledge-maintenance/content-standard.md) |
| 赛事分工原包 | [总入口](competition-research/README.md) · [1—89](competition-research/tongji-2026-001-089/README.md) · [90—130](curated-research-90-130.md) · [131—255](curated-competition-package.txt) |
| 赛事知识交付与评测 | [交付说明](competition-delivery.md) · [正式交付包](../deliverables/competition-knowledge-v1/README.md) · [评测](competition-evaluation/README.md) |
| 全国科研资料与接入 | [最新交付](releases/research-ai-20261007.md) · [资料包](research-national/20261007/README.md) |
| 同济本科科研原包 | [90 条资料](undergraduate-research/tongji-20261003-verified/README.md) |
| 快讯与早期科研人工内容 | [编辑说明](undergraduate-labs.md)；科研数据库接入按最新交付文档 |

## 历史采集与设计

历史采集实现仍保留，不是当前手动资料维护的必选步骤：[目录覆盖](competition-catalog-coverage.md)、[发现与监测](competition-discovery.md)、[提取上架](catalog-publication.md)、[采集实现](ingestion-implementation.md)、[来源清单](competition-sources.md)。这些文档中的运行数量需按记录日期理解。

[产品范围](product-scope.md)、[前端实现记录](frontend-implementation.md)用于理解已有设计；[历史归档](archive/README.md)保存早期方案、阶段测试和进度。最新路由、接口及配置以当前源码与对应接入文档为准。
