param(
    [ValidateSet('start', 'stop', 'status')]
    [string]$Action = 'start',
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173,
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8000,
    [string]$PythonPath,
    [string]$NodePath = 'node.exe'
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repositoryRoot 'backend'
$frontendRoot = Join-Path $repositoryRoot 'frontend'
$runtimeRoot = Join-Path $repositoryRoot ".local\dev\$FrontendPort-$BackendPort"
$statePath = Join-Path $runtimeRoot 'processes.json'
$managePath = Join-Path $backendRoot 'manage.py'
$vitePath = Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'

function Get-OwnedProcess($Entry) {
    if (-not $Entry) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($Entry.id)" -ErrorAction SilentlyContinue
    if (-not $process) { return $null }
    # ConvertFrom-Json may parse ISO timestamps into DateTime depending on PowerShell version.
    $created = ([datetime]$process.CreationDate).ToUniversalTime().Ticks
    $expectedCreated = ([datetime]$Entry.created).ToUniversalTime().Ticks
    if ($created -ne $expectedCreated -or -not $process.CommandLine -or -not $process.CommandLine.Contains($Entry.marker)) {
        throw "Process $($Entry.id) no longer matches this launcher. It will not be stopped."
    }
    return $process
}

function New-ProcessEntry($Process, [string]$Marker) {
    $metadata = Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
    if (-not $metadata) { throw "A service exited before startup completed. Check $runtimeRoot" }
    return @{
        id = $Process.Id
        created = ([datetime]$metadata.CreationDate).ToUniversalTime().ToString('o')
        marker = $Marker
    }
}

function Get-PortListener([int]$Port) {
    return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
}

$state = if (Test-Path -LiteralPath $statePath) {
    Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
} else { $null }

if ($Action -ne 'start') {
    if (-not $state) {
        Write-Output "No saved development services for ports $FrontendPort/$BackendPort."
        exit 0
    }
    foreach ($name in @('frontend', 'backend')) {
        $process = Get-OwnedProcess $state.$name
        if ($Action -eq 'stop' -and $process) { Stop-Process -Id $process.ProcessId }
        $status = if ($process -and $Action -eq 'status') { 'running' } else { 'stopped' }
        Write-Output "$name`: $status"
    }
    if ($Action -eq 'stop') { Remove-Item -LiteralPath $statePath }
    exit 0
}

if ($FrontendPort -eq $BackendPort) { throw 'FrontendPort and BackendPort must be different.' }
if ($state) {
    foreach ($name in @('frontend', 'backend')) {
        if (Get-OwnedProcess $state.$name) {
            throw "A saved $name process is still running. Use -Action stop with the same port pair before restarting."
        }
    }
}
foreach ($port in @($FrontendPort, $BackendPort)) {
    if (Get-PortListener $port) {
        throw "Port $port is occupied. Stop its existing service or choose another port; no process was changed."
    }
}
if (-not $PythonPath) { $PythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe' }
$pythonExecutable = (Get-Command $PythonPath -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$nodeExecutable = (Get-Command $NodePath -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
if (-not (Test-Path -LiteralPath $vitePath)) { throw 'Install frontend dependencies with npm.cmd ci first.' }
if (-not (Test-Path -LiteralPath (Join-Path $backendRoot '.env'))) {
    throw 'Configure backend/.env and PostgreSQL first; see docs/backend-development.md.'
}
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$overrides = @{
    PYTHONIOENCODING = 'utf-8'
    PYTHONUNBUFFERED = '1'
    DJANGO_PUBLIC_ORIGIN = "http://127.0.0.1:$FrontendPort"
    DJANGO_CSRF_TRUSTED_ORIGINS = "http://127.0.0.1:$FrontendPort,http://localhost:$FrontendPort"
    DEV_SERVER_PORT = [string]$FrontendPort
    DEV_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
}
$previous = @{}
$started = @()
try {
    foreach ($name in $overrides.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $overrides[$name], 'Process')
    }
    $backend = Start-Process -FilePath $pythonExecutable -WorkingDirectory $backendRoot `
        -ArgumentList @(('"{0}"' -f $managePath), 'runserver', "127.0.0.1:$BackendPort", '--noreload') `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeRoot 'backend.out.log') `
        -RedirectStandardError (Join-Path $runtimeRoot 'backend.err.log')
    $started += $backend
    $frontend = Start-Process -FilePath $nodeExecutable -WorkingDirectory $frontendRoot `
        -ArgumentList @(('"{0}"' -f $vitePath)) -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeRoot 'frontend.out.log') `
        -RedirectStandardError (Join-Path $runtimeRoot 'frontend.err.log')
    $started += $frontend
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($backend.HasExited -or $frontend.HasExited) {
            throw "A service exited during startup. Check logs in $runtimeRoot"
        }
        if ((Get-PortListener $BackendPort) -and (Get-PortListener $FrontendPort)) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Service startup timed out. Check logs in $runtimeRoot" }
    @{
        backend = New-ProcessEntry $backend $managePath
        frontend = New-ProcessEntry $frontend $vitePath
    } | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    Write-Output "Website: http://127.0.0.1:$FrontendPort/"
    Write-Output "Admin:   http://127.0.0.1:$BackendPort/admin/"
    Write-Output "Logs:    $runtimeRoot"
} catch {
    foreach ($process in $started) {
        if (-not $process.HasExited) { $process.Kill() }
    }
    throw
} finally {
    foreach ($name in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
