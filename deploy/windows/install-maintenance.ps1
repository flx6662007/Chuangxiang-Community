param([ValidateSet('all', 'ingest', 'settle')][string]$Task = 'all')
# 无密码、当前用户登录期间运行；电脑需开机且 PostgreSQL 可连接。
$ErrorActionPreference = 'Stop'
$runner = (Resolve-Path (Join-Path $PSScriptRoot 'run-maintenance.ps1')).Path
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited
$taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$shellPath = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
foreach ($item in @(
    @{Name='Chuangxiang-CompetitionSync'; Mode='ingest'; Interval=(New-TimeSpan -Hours 6)},
    @{Name='Chuangxiang-TeamSettlement'; Mode='settle'; Interval=(New-TimeSpan -Minutes 1)}
)) {
    if ($Task -ne 'all' -and $Task -ne $item.Mode) { continue }
    $action = New-ScheduledTaskAction -Execute $shellPath -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $runner + '" -Task ' + $item.Mode)
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval $item.Interval
    Register-ScheduledTask -TaskName $item.Name -Action $action -Trigger $trigger -Principal $taskPrincipal -Settings $taskSettings -Description '创享本机维护；日志在仓库 .local/maintenance。' -Force | Select-Object TaskName, State
}
