# 赛事知识系统交付包

资料版本：`874ccd5c6dddf794`。新版资料采用一条独立导入与检索链路。

| 文件 | 用途 |
| --- | --- |
| [赛事成品包](competition-materials-v1-874ccd5c6dddf794.zip) | HTML、CSV、20 项样本、JSON、JSONL；解压后打开 `index.html` |
| [导入与检索接入包](competition-integration-v1-874ccd5c6dddf794.zip) | 统一导入命令、检索代码、依赖、评测集、工具与说明 |
| [维护包](competition-maintenance-v1-874ccd5c6dddf794.zip) | 三个独立导入 JSON、来源、处理记录和重建输入 |
| [文件与 SHA-256 清单](manifest.json) | 三个 ZIP 及每个文件的大小和校验值 |

接入包和维护包保留仓库相对路径，用于本项目；赛事成品包可以单独阅读。从[交付说明](../../docs/competition-delivery.md)开始，按[接入说明](../../docs/competition-search-handoff.md)完成环境准备、统一导入和数据库检索。聊天同学调用 `search_competitions()` 获取新版正文、匹配理由和来源。
