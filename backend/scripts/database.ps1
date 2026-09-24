param(
    [ValidateSet('start', 'stop', 'status')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path -Parent $PSScriptRoot
$runtimeConfig = Join-Path $backendRoot '.local\postgresql-paths.json'
if (-not (Test-Path -LiteralPath $runtimeConfig)) {
    throw 'Local PostgreSQL paths are not configured. See the local environment setup notes.'
}
$runtimePaths = Get-Content -LiteralPath $runtimeConfig -Raw -Encoding UTF8 | ConvertFrom-Json
$pgCtl = Join-Path $runtimePaths.bin 'pg_ctl.exe'
$dataDir = $runtimePaths.data
$logPath = Join-Path $dataDir 'server.log'

if (-not (Test-Path -LiteralPath $pgCtl)) {
    throw 'Local PostgreSQL binaries are missing. See the local environment setup notes.'
}
if (-not (Test-Path -LiteralPath (Join-Path $dataDir 'PG_VERSION'))) {
    throw 'Local PostgreSQL data directory has not been initialized.'
}

if ($Action -eq 'status') {
    & $pgCtl -D $dataDir status
    exit $LASTEXITCODE
}

& $pgCtl -D $dataDir status *> $null
$isRunning = $LASTEXITCODE -eq 0
if ($Action -eq 'start' -and $isRunning) {
    Write-Output 'PostgreSQL is already running.'
    exit 0
}
if ($Action -eq 'stop' -and -not $isRunning) {
    Write-Output 'PostgreSQL is already stopped.'
    exit 0
}

if ($Action -eq 'start') {
    $pgArguments = @('-D', ('"{0}"' -f $dataDir), '-l', ('"{0}"' -f $logPath), '-w', '-t', '30', 'start')
} else {
    $pgArguments = @('-D', ('"{0}"' -f $dataDir), '-m', 'fast', '-w', '-t', '30', 'stop')
}

$pgProcess = Start-Process -FilePath $pgCtl -ArgumentList $pgArguments -WindowStyle Hidden -PassThru
if (-not $pgProcess.WaitForExit(45000)) {
    throw "PostgreSQL $Action timed out. Check the local database log: $logPath"
}
if ($pgProcess.ExitCode -ne 0) {
    throw "PostgreSQL $Action failed. Check the local database log: $logPath"
}
Write-Output "PostgreSQL $Action completed."
