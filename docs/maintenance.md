# 本机定时任务

代码提供 Windows 免费运行方案；是否已在某台电脑安装并运行，以该电脑的任务计划与日志为准。无需购买服务器，但电脑必须开机、用户保持登录，且 PostgreSQL 和网络可用。浏览器是否打开不影响采集。

## 首次准备

在仓库的 `backend` 目录执行。先安装 `requirements.txt`、执行已有迁移，再初始化固定选项：

```powershell
.\.venv\Scripts\python.exe manage.py seed_recruitment_options
```

由具备赛事维护权限的管理员运行首次采集。`12` 仅为编号示例，要替换为本机实际管理员编号；项目不提供默认密码，也不要求提交密码到命令或 GitHub。

```powershell
.\.venv\Scripts\python.exe manage.py sync_competitions --init-sources --actor-id 12 --trigger manual --auto-accept --enable-recruitment
```

`--auto-accept` 允许已配置官方来源的完整规则结果进入正式赛事库；重要改动和人工修订冲突仍留待复核。`--enable-recruitment` 只为官方明确允许组队、人数上限与未来报名日期均明确的新赛事设置平台招募期限：北京时间报名截止日期前一天 00:00 停招。它是平台提前停止招募的规则，不冒充官方精确截止时刻。

已有虚构样例的开发库可运行下列命令退出公开展示。它只识别仓库种子的固定编码与虚构标记，保留历史和关联队伍，不删除用户数据：

```powershell
.\.venv\Scripts\python.exe manage.py retire_demo_data --actor-id 12
```

## 安装和检查

回到仓库根目录运行：

```powershell
.\deploy\windows\install-maintenance.ps1
Get-ScheduledTask -TaskName 'Chuangxiang-*'
Get-ScheduledTaskInfo -TaskName 'Chuangxiang-CompetitionSync'
Get-ScheduledTaskInfo -TaskName 'Chuangxiang-TeamSettlement'
```

脚本注册当前用户的两项任务；再次执行会更新同名任务，不创建重复调度：

可先单独安装不依赖采集账号的组队结算：`./deploy/windows/install-maintenance.ps1 -Task settle`。待真实来源初始化完成，再以 `-Task ingest` 安装采集任务；不带参数时安装两项。

| 任务 | 周期 | 内容 |
| --- | --- | --- |
| `Chuangxiang-CompetitionSync` | 每 6 小时 | 获取启用官方来源、保存新版本和候选，受控采纳 |
| `Chuangxiang-TeamSettlement` | 每分钟 | 结算招募到期、退出／移除及解散请求的固定期限 |

任务在隐藏窗口运行，不存储 Windows 密码。休眠和关机期间无法运行；恢复后由系统尽早补跑。每分钟结算可能产生约一分钟可见延迟，但关键写入也会先检查期限，不能通过延迟结算抢占过期名额。

手动触发与停止后续调度：

```powershell
Start-ScheduledTask -TaskName 'Chuangxiang-CompetitionSync'
Start-ScheduledTask -TaskName 'Chuangxiang-TeamSettlement'
Disable-ScheduledTask -TaskName 'Chuangxiang-CompetitionSync'
Disable-ScheduledTask -TaskName 'Chuangxiang-TeamSettlement'
```

`LastTaskResult=0` 表示上次脚本正常退出；`267009` 表示仍在运行。仍须检查 `LastRunTime` 是否是本次执行，不能把从未运行时的默认值当成成功。

## 日志和维护

- 脚本最新日志在仓库 `.local/maintenance/ingest-latest.log` 和 `settle-latest.log`，不提交 GitHub。
- 每次采集的持久记录在 Admin 的 `FetchRun`，原文在 `SourceVersion`，候选与采纳结论在 `ProcessingResult`。
- 来源超时或解析失败不会清空已发布数据；查看失败原因，修正适配器后手动重试。
- 想增加官网，应添加有样本和测试的适配器。只粘贴新网址不会自动理解任意网页。
- 后续迁移到持续运行的 Linux 主机，继续调用同一 Django 命令，再用主机调度替代 Windows 任务计划。
