param([ValidateSet('all', 'ingest', 'settle')][string]$Task = 'all')
# 无密码、当前用户登录期间运行；电脑需开机且 PostgreSQL 可连接。
$ErrorActionPreference = 'Stop'
$runner = (Resolve-Path (Join-Path $PSScriptRoot 'run-maintenance.py')).Path
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pythonwPath = Join-Path $repoRoot 'backend\.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath)) { throw 'Create backend/.venv and install its dependencies first.' }
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited
$taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
foreach ($item in @(
    @{Name='Chuangxiang-CompetitionSync'; Mode='ingest'; Interval=(New-TimeSpan -Hours 6)},
    @{Name='Chuangxiang-TeamSettlement'; Mode='settle'; Interval=(New-TimeSpan -Minutes 1)}
)) {
    if ($Task -ne 'all' -and $Task -ne $item.Mode) { continue }
    # pythonw has no console; its children also use CREATE_NO_WINDOW.
    $action = New-ScheduledTaskAction -Execute $pythonwPath -Argument ('"' + $runner + '" --task ' + $item.Mode) -WorkingDirectory $repoRoot
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval $item.Interval
    Register-ScheduledTask -TaskName $item.Name -Action $action -Trigger $trigger -Principal $taskPrincipal -Settings $taskSettings -Description '创享本机维护；日志在仓库 .local/maintenance。' -Force | Select-Object TaskName, State
}
