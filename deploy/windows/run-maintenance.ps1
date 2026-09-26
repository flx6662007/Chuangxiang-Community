param([ValidateSet('ingest', 'settle')][string]$Task = 'ingest')
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$backendPath = Join-Path $repoRoot 'backend'
$pythonPath = Join-Path $backendPath '.venv\Scripts\python.exe'
$logDir = Join-Path $repoRoot '.local\maintenance'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logPath = Join-Path $logDir ($Task + '-latest.log')
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '请先创建 backend/.venv 并安装依赖。' }
Push-Location -LiteralPath $backendPath
try {
    ('Started: ' + (Get-Date).ToString('o')) | Set-Content -LiteralPath $logPath -Encoding utf8
    # Windows PowerShell 5.1 的原生重定向默认为 UTF-16；统一日志为 UTF-8。
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $env:PYTHONIOENCODING = 'utf-8'
    if ($Task -eq 'ingest') {
        & $pythonPath manage.py sync_competitions --trigger scheduled --auto-accept --enable-recruitment 2>&1 | Out-File -LiteralPath $logPath -Append -Encoding utf8
    } else {
        & $pythonPath manage.py settle_team_deadlines 2>&1 | Out-File -LiteralPath $logPath -Append -Encoding utf8
    }
    $resultCode = $LASTEXITCODE
    ('Finished: ' + (Get-Date).ToString('o') + '; exit=' + $resultCode) | Add-Content -LiteralPath $logPath
    exit $resultCode
} finally { Pop-Location }
