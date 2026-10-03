# 同济2026目录90—130资料交付与入库

资料包下载：[GitHub Release](https://github.com/flx6662007/Chuangxiang-Community/releases/tag/tongji-2026-90-130-20261003)。下载`tongji-2026-90-130-20261003.zip`及`curated-delivery-90-130.json`，校验后解压到自己的持久目录。代码及操作说明在main，附件通过Release交付；本机数据库已导入不表示队友库已经入库。

本轮范围为2026090—2026130，共41项，分90—114及115—130两批。资料包保存在
`D:\创享科创信息与组队服务平台\赛事资料库\同济2026-90-130`。

`整理底稿.json`是唯一事实维护源。`总索引.xlsx`、逐编号逐届次的赛事说明、学习导读、来源与缺口、`导入清单.json`及JSONL均由底稿生成；原件集中按SHA-256存放，课程和视频保留链接与导读。

41项都有处理记录。当前采用资料中31项取得规则或正式通知，6项细则不全，3项只有报道，1项身份未确认；不代表41项完整规则全部验收。学习资源148条关联、97份去重，模拟法庭第111项仅2份。第118项找到的同济校赛无法确认对应目录省级赛事，因此只保存目录知识记录，不建具体赛事。往届规则和历史截止独立归档；其他学校选拔通知不作为同济校内截止。

## 依赖与数据关系

依赖已交付的`tongji-2026-131-255`包。本包新增49个具体届次候选、80个学习资源、119个知识文档；复用原包2个SCIP+届次及17个资源。第122、123项关联同一届上海力学赛，第128项增补原第135项赛事的目录关联。资源与目录通过知识文档关联；通用资料不强制指定赛事届次，不创建虚构届次。

复用清单包括原包标识及载荷哈希。原包应先入库且版本一致；缺失或被人工更改会拒绝导入并回滚。复用赛事只增补目录关联，原包仍拥有正文和来源；新旧包重复导入均不重复建对象。接收者若尚无原包，可从此前[资料包发布页](https://github.com/flx6662007/Chuangxiang-Community/releases/tag/tongji-2026-131-255-20261002)取得依赖。不会自动下载或执行依赖。

## 离线命令

在工程根目录使用项目Python，替换下方包路径和管理员ID。先检查附件完整性：

```powershell
backend/.venv/Scripts/python.exe backend/manage.py import_curated_competitions "资料包路径/导入清单.json" --report "校验报告.json"
```

预演在事务内执行后回滚，不读取赛事界面：

```powershell
backend/.venv/Scripts/python.exe backend/manage.py import_curated_competitions "资料包路径/导入清单.json" --actor-id <管理员ID> --preview --report "预演报告.json"
```

正式接收时先审核目标库、依赖版本和待导入内容，再给执行清单设置`review.status=approved`、`reviewed_by`、`reviewed_on`，用`--apply`替换`--preview`。可重复指定`--batch 1`或`--batch 2`；不指定时导入全部41项。本机执行记录的账号ID不能照抄到队友库。

本次仅按用户授权入本地开发库草稿。事实底稿仍`pending`，本机执行清单中的许可标记不表示全部事实已审核。Competition/Resource保持draft，KnowledgeDocument保持draft、来源未验证、组队关闭；未审核材料不进入学生AI检索。没有发布、分类分配、前端改动、公开HTTP接口、向量库或模型调用。

## 维护与重新生成

修改底稿后离线生成，其本身不访问网络、不写库：

```powershell
backend/.venv/Scripts/python.exe scripts/build-research-package.py "资料包路径/整理底稿.json" --dependency "原包路径/导入清单.json"
```

Excel生成脚本为`scripts/build-research-index.mjs`，仅交付方使用提供的Artifact Tool运行时生成；接收与入库不依赖它。新通知应新增实际届次，不能把旧期限改写为当前。扫描件的自动提取文本不视为校对完成；关键条款核对范围与缺失内容分别注明。

代码只扩展离线包声明范围及显式跨包复用，保留旧包默认131—255范围与原有覆盖保护，不修改模型或发布流程。验收文件保存在包内`验收报告/`；现有未提交的分类及自动采集相关修改属于此前工作，本轮没有纳入操作。
