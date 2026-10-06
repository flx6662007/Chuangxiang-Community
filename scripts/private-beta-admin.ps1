param(
    [ValidateSet('start', 'stop', 'status')][string]$Action = 'start',
    [string]$EnvFile,
    [string]$PythonPath,
    [ValidateRange(1, 65535)][int]$Port = 8011
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repositoryRoot 'backend'
if (-not $EnvFile) { $EnvFile = Join-Path $repositoryRoot '.local\private-beta\chuangxiang_beta_20261006_ai\.env' }
$EnvFile = [IO.Path]::GetFullPath($EnvFile)
$runtimeRoot = Split-Path -Parent $EnvFile
$statePath = Join-Path $runtimeRoot 'admin-process.json'
$markers = @('config.private_beta', '--local-admin', $EnvFile, "--port $Port")

function Get-OwnedProcess($Entry) {
    if (-not $Entry) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($Entry.id)" -ErrorAction SilentlyContinue
    if (-not $process) { return $null }
    if (([datetime]$process.CreationDate).ToUniversalTime().Ticks -ne ([datetime]$Entry.created).ToUniversalTime().Ticks -or
        $process.ExecutablePath -ine $Entry.executable -or -not $process.CommandLine) {
        # A reused PID is not our service; an occupied port is checked separately.
        return $null
    }
    foreach ($marker in $Entry.markers) {
        if (-not $process.CommandLine.Contains([string]$marker)) { return $null }
    }
    return $process
}

function New-Entry([int]$ProcessId) {
    $metadata = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $metadata -or -not $metadata.ExecutablePath) { throw 'Admin exited before its identity could be saved.' }
    return @{
        id = $metadata.ProcessId
        created = ([datetime]$metadata.CreationDate).ToUniversalTime().ToString('o')
        executable = $metadata.ExecutablePath
        markers = $markers
    }
}

function Save-State($State) {
    $temporary = "$statePath.tmp"
    $State | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $statePath -Force
}

function Update-Children($State) {
    if (-not (Get-OwnedProcess $State.launcher)) { return }
    $parents = @([int]$State.launcher.id)
    for ($level = 0; $level -lt 3 -and $parents.Count -gt 0; $level++) {
        $nextParents = @()
        foreach ($parentId in $parents) {
            foreach ($child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$parentId" -ErrorAction SilentlyContinue)) {
                if (-not $child.CommandLine -or -not $child.ExecutablePath) { continue }
                $matches = $true
                foreach ($marker in $markers) { if (-not $child.CommandLine.Contains($marker)) { $matches = $false } }
                if (-not $matches -or ([datetime]$child.CreationDate).ToUniversalTime().Ticks -lt
                    ([datetime]$State.launcher.created).ToUniversalTime().Ticks) { continue }
                $nextParents += [int]$child.ProcessId
                if (@($State.children | Where-Object { $_.id -eq $child.ProcessId }).Count -eq 0) {
                    $State.children += New-Entry $child.ProcessId
                    Save-State $State
                }
            }
        }
        $parents = $nextParents
    }
}

function Stop-OwnedProcess($Entry) {
    $process = Get-OwnedProcess $Entry
    if ($process) {
        Stop-Process -Id $process.ProcessId -ErrorAction Stop
        Wait-Process -Id $process.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $runtimeRoot -PathType Container)) {
    if ($Action -eq 'start') { throw 'Prepare the private beta environment first.' }
    Write-Output 'Local beta admin: stopped'
    exit 0
}
$lock = $null
$state = $null
$started = $null
try {
    $lock = [IO.File]::Open((Join-Path $runtimeRoot 'admin-launcher.lock'),
        [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($state.env_file -ine $EnvFile) { throw 'Admin state belongs to another environment file.' }
        foreach ($entry in @($state.children) + @($state.launcher)) { $null = Get-OwnedProcess $entry }
    }
    if ($Action -ne 'start') {
        if ($Action -eq 'stop' -and $state) {
            foreach ($entry in @($state.children) + @($state.launcher)) { Stop-OwnedProcess $entry }
            Remove-Item -LiteralPath $statePath
            Write-Output 'Local beta admin: stopped'
        } elseif ($state -and (Get-OwnedProcess $state.launcher)) {
            Write-Output "Local beta admin: http://127.0.0.1:$($state.port)/admin/"
        } else { Write-Output 'Local beta admin: stopped' }
        return
    }
    if ($state) {
        foreach ($entry in @($state.children) + @($state.launcher)) {
            if (Get-OwnedProcess $entry) { throw 'The saved local admin is already running.' }
        }
    }
    if (@(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).Count) {
        throw "Port $Port is occupied; no existing process was changed."
    }
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) { throw 'The private .env file is missing.' }
    if ($EnvFile.Contains('"')) { throw 'The environment path cannot contain a quote.' }
    if (-not $PythonPath) { $PythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe' }
    $pythonExecutable = (Get-Command $PythonPath -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $started = Start-Process -FilePath $pythonExecutable -WorkingDirectory $backendRoot `
        -ArgumentList @('-m', 'config.private_beta', '--local-admin', '--port', [string]$Port, '--env-file', ('"{0}"' -f $EnvFile)) `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'admin.out.log') `
        -RedirectStandardError (Join-Path $runtimeRoot 'admin.err.log')
    $state = @{ version = 1; env_file = $EnvFile; port = $Port; launcher = (New-Entry $started.Id); children = @() }
    Save-State $state
    $ready = $false
    $adminReadyClock = [Diagnostics.Stopwatch]::StartNew()
    while ($adminReadyClock.Elapsed.TotalSeconds -lt 180) {
        if ($started.HasExited) { throw 'Local admin exited; inspect admin.err.log.' }
        Update-Children $state
        $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
        if ($listeners.Count) {
            $owned = @($state.launcher.id) + @($state.children | ForEach-Object { $_.id })
            if (@($listeners | Where-Object { $_.OwningProcess -notin $owned -or $_.LocalAddress -ne '127.0.0.1' }).Count) {
                throw 'Admin listener identity or loopback binding did not match.'
            }
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'Local admin did not become ready within 180 seconds.' }
    Write-Output "Local beta admin: http://127.0.0.1:$Port/admin/"
} catch {
    $failure = $_
    if ($started) {
        if ($state) {
            try { Update-Children $state } catch { }
            foreach ($entry in @($state.children) + @($state.launcher)) {
                try { Stop-OwnedProcess $entry } catch { }
            }
        }
        if (-not $started.HasExited) { $started.Kill() }
    }
    throw $failure
} finally {
    if ($lock) { $lock.Dispose() }
}
