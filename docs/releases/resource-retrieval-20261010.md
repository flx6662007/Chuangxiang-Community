# 学习资料检索修复

日期：2026-10-10。针对同一资料换问法后漏检、赛事关联说明错误、推荐偏题和正文入口丢失进行修复。

## 改动

| 文件或模块 | 作用 |
| --- | --- |
| `backend/ai_services/resource_retrieval.py`（新增） | 中文短语、英文词边界、名称简称、精确课程编号、资料类型与相关性筛选 |
| `backend/ai_services/unified.py`、`router.py` | 读取真实赛事目录与具名关联；区分资料请求、赛事请求和科研介绍，保持公开范围 |
| `backend/ai_services/unified_index.py` | 资源语义索引纳入赛事名称、别名与关联；schema 升至 3，关联变化后旧索引失效 |
| `backend/ai_services/fusion.py`、`chat.py` | 来源按检索相关性分配；保留登记的项目与文档入口，避免把本轮未检出答成平台未收录 |
| `frontend/src/api/aiResponse.js`、`utils/aiMarkdown.js`、`components/AICompetitionAssistant.vue` | 正文链接与来源白名单一致；资料推荐打开站内详情；公开队伍来源、推荐与会话编号保持一致 |
| 对应后端与前端测试 | 覆盖简称误匹配、关联丢失、纯语义回退、缺失课程、科研边界、来源排序和链接处理 |
| `scripts/evaluate-resource-chat-retrieval.py`、`docs/resource-evaluation/` | 27 个固定问法及只读回归工具，检查最终来源、推荐与关联上下文 |

未增加依赖或修改数据库结构。资源、赛事和原始资料包沿用现有数据。

## 本机验证

使用当前本机 322 条公开资源，联网补充关闭。测试读取完整候选库，不只加载预期答案。

| 检查 | 结果 |
| --- | --- |
| AI 后端测试 | 187/187 通过 |
| 前端测试 | 75/75 通过 |
| 前端生产构建 | 通过 |
| 27 题 × 智能/资源模式，当前语义配置 | 54/54 通过，无检索警告 |
| 同组问题强制关键词回退 | 54/54 通过；只有预期的关闭索引提示 |
| 最终版本真实 SSE 问答 | 20/20 请求成功；原 14 个库内正例目标命中从 8/14 提升至 14/14 |
| 真实多轮追问 | Python 教程与 Better BibTeX 两例均找到目标 |
| 实际前端解析与渲染 | 20 份回答的来源和卡片均保留；正文出现的 22 个登记入口均可渲染为链接 |
| 页面操作 | RM/C 板问法找到官方例程；最终版蓝桥杯 Python 问法只推荐 Python 官方教程，关联名称正确 |

人工读取了最终 20 份回答：未再出现本轮发现的蓝桥杯关联否认或 Zotero 正文链接省略。上述命中率是固定样本结果，不代表任意问题的整体准确率，也不等于每项补充推荐都最优。

复用已安装依赖的 Python，核心验证命令为：

```powershell
python backend/manage.py test ai_services --settings=config.test_settings --noinput
python scripts/evaluate-resource-chat-retrieval.py --mode smart --mode resource --require-semantic --output .local/resource-evaluation/configured.json
python scripts/evaluate-resource-chat-retrieval.py --mode smart --mode resource --keyword-only --output .local/resource-evaluation/keyword.json
```

在 `frontend/` 执行 `npm test` 和 `npm run build`。完整评测判定与边界见[资源评测说明](../resource-evaluation/README.md)。

## 运行配置

推送前在独立工作区合并远端 `main`（`ad9f247`），保留首轮问题理解、新对话、站内编号及最新界面更新。合并后重新执行 AI 后端测试，198/198 通过；前端测试与生产构建通过，路径与 diff 检查通过。上表真实问答和 108 项检索检查来自合并前的修复版本，本次合并未重新调用付费模型复测。

本机已生成含 380 个公开文本片段的 schema 3 资源索引，设置 `backend/.env` 的 `UNIFIED_SEMANTIC_INDEX`，重启本机 5173/8000 服务并验证。模型、索引、配置、原始响应及日志留在忽略目录，不进入仓库。

其他电脑拉取代码后，按 [AI 接入](../ai-v3.md#资料与索引)重建并配置自己的索引；未配置时仍可用关键词检索。代码同步不会同步数据库、密钥、索引或正在运行的其他内测服务。

## 后续关注

- 指定资料未收录时，相关替代仍可能偏宽。例如廖雪峰教程未找到，但附带 MuJoCo、napari；回答已说明并非所求教程。
- 多轮问题的回答可以正确选出 Better BibTeX，而卡片仍把相关的 Zotero Skills 排在前面；仍有调整排序的空间。
- 宽泛备赛问题可能同时推荐教程与辅助工具。当前重点是找到目标并避免明显偏题，尚未实现按个人基础自动生成精确学习路线。
- 本轮没有重新验证全部外链的实时可达性；资料更新后应重建索引并复跑题集。
