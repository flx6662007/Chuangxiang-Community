param(
    [ValidateSet('start', 'stop', 'status')]
    [string]$Action = 'start',
    [string]$EnvFile,
    [string]$PythonPath,
    [ValidateRange(1, 65535)]
    [int]$Port = 8010
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repositoryRoot 'backend'
if (-not $EnvFile) {
    $EnvFile = Join-Path $repositoryRoot '.local\private-beta\chuangxiang_beta_20261006_ai\.env'
}
$EnvFile = [IO.Path]::GetFullPath($EnvFile)
$runtimeRoot = Split-Path -Parent $EnvFile
$statePath = Join-Path $runtimeRoot 'processes.json'
$pythonPathFile = Join-Path $runtimeRoot 'python-path.txt'
$tunnelExecutable = Join-Path $repositoryRoot '.local\tools\cloudflared.exe'
$tunnelOutput = Join-Path $runtimeRoot 'tunnel.out.log'
$tunnelError = Join-Path $runtimeRoot 'tunnel.err.log'

function Get-OwnedProcess($Entry) {
    if (-not $Entry) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($Entry.id)" -ErrorAction SilentlyContinue
    if (-not $process) { return $null }
    $created = ([datetime]$process.CreationDate).ToUniversalTime().Ticks
    $expectedCreated = ([datetime]$Entry.created).ToUniversalTime().Ticks
    if ($created -ne $expectedCreated -or -not $process.CommandLine -or
        $process.ExecutablePath -ine $Entry.executable) {
        # A reused PID is not our service. Never stop it or block recovery of stale state.
        return $null
    }
    foreach ($marker in $Entry.markers) {
        if (-not $process.CommandLine.Contains([string]$marker)) {
            return $null
        }
    }
    return $process
}

function New-ProcessEntry($Process, [string[]]$Markers) {
    $metadata = Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)" -ErrorAction SilentlyContinue
    if (-not $metadata -or -not $metadata.ExecutablePath) {
        throw "A service exited before its identity was saved. Check logs in $runtimeRoot"
    }
    return @{
        id = $Process.Id
        created = ([datetime]$metadata.CreationDate).ToUniversalTime().ToString('o')
        executable = $metadata.ExecutablePath
        markers = $Markers
    }
}

function Save-State($State) {
    $temporaryPath = "$statePath.tmp"
    $State | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $statePath -Force
}

function Get-PortListener([int]$ListenPort) {
    return @(Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue)
}

function Stop-OwnedProcess($Entry) {
    $process = Get-OwnedProcess $Entry
    if ($process) {
        Stop-Process -Id $process.ProcessId -ErrorAction Stop
        Wait-Process -Id $process.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
}

function Update-BackendChildren($State) {
    if (-not (Get-OwnedProcess $State.backend)) { return }
    # Windows virtualenv launchers may start a second Python process. Record only
    # descendants carrying this exact module, environment path, and port.
    $parents = @([int]$State.backend.id)
    for ($level = 0; $level -lt 3 -and $parents.Count -gt 0; $level++) {
        $nextParents = @()
        foreach ($parentId in $parents) {
            $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$parentId" -ErrorAction SilentlyContinue)
            foreach ($child in $children) {
                if (-not $child.CommandLine -or -not $child.ExecutablePath -or
                    -not $child.CommandLine.Contains('config.private_beta') -or
                    -not $child.CommandLine.Contains($EnvFile) -or
                    -not $child.CommandLine.Contains("--port $($State.port)")) { continue }
                if (([datetime]$child.CreationDate).ToUniversalTime().Ticks -lt
                    ([datetime]$State.backend.created).ToUniversalTime().Ticks) { continue }
                $nextParents += [int]$child.ProcessId
                if (@($State.backend_children | Where-Object { $_.id -eq $child.ProcessId }).Count -eq 0) {
                    $State.backend_children += @{
                        id = $child.ProcessId
                        created = ([datetime]$child.CreationDate).ToUniversalTime().ToString('o')
                        executable = $child.ExecutablePath
                        markers = @('config.private_beta', $EnvFile, "--port $($State.port)")
                    }
                    Save-State $State
                }
            }
        }
        $parents = $nextParents
    }
}

function Write-Origin([string]$Origin) {
    $contents = [IO.File]::ReadAllText($EnvFile)
    $pattern = '(?m)^[ \t]*(?:export[ \t]+)?PRIVATE_BETA_ORIGIN[ \t]*=[^\r\n]*'
    $matches = [regex]::Matches($contents, $pattern)
    if ($matches.Count -gt 1) { throw 'PRIVATE_BETA_ORIGIN appears more than once in the private environment file.' }
    if ($matches.Count -eq 1) {
        $contents = [regex]::Replace($contents, $pattern, "PRIVATE_BETA_ORIGIN=$Origin")
    } else {
        $contents = $contents.TrimEnd("`r", "`n") + "`r`nPRIVATE_BETA_ORIGIN=$Origin`r`n"
    }
    # Keep all other settings private and unchanged. The directory owns its access policy.
    [IO.File]::WriteAllText($EnvFile, $contents, (New-Object Text.UTF8Encoding($false)))
}

function Update-InvitationOrigins([string]$Origin) {
    # Only these generated handoff files belong to this launcher; never search
    # surrounding files or print their private account credentials.
    $invitationFiles = @(
        (Join-Path $runtimeRoot '内测使用说明-仅负责人.txt'),
        (Join-Path $runtimeRoot '内测账号清单-仅负责人.md')
    )
    foreach ($number in 1..50) {
        $invitationFiles += Join-Path $runtimeRoot ('invitations\内测邀请-{0:00}.txt' -f $number)
        $invitationFiles += Join-Path $runtimeRoot ('invitations\内测邀请-{0:00}.md' -f $number)
    }
    foreach ($invitationFile in $invitationFiles) {
        if (-not (Test-Path -LiteralPath $invitationFile -PathType Leaf)) { continue }
        $originalText = [IO.File]::ReadAllText($invitationFile)
        $updatedText = [regex]::Replace($originalText,
            'https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\b', $Origin)
        if ($updatedText -cne $originalText) {
            [IO.File]::WriteAllText($invitationFile, $updatedText, (New-Object Text.UTF8Encoding($false)))
        }
    }
}

if (-not (Test-Path -LiteralPath $runtimeRoot -PathType Container)) {
    if ($Action -eq 'start') { throw 'Prepare the private environment file before starting the beta.' }
    Write-Output 'No saved private beta services.'
    exit 0
}

# Serialize launches/stops using this private environment, including partial startups.
$lock = $null
$started = @()
$state = $null
$originalEnvironment = $null
$originChanged = $false
try {
    try {
        $lock = [IO.File]::Open((Join-Path $runtimeRoot 'launcher.lock'),
            [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    } catch { throw 'Another launcher is using this private beta environment. Try again after it finishes.' }
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($state.env_file -ine $EnvFile) { throw 'Saved beta state belongs to a different environment file.' }
    }

    if ($Action -ne 'start') {
        if (-not $state) {
            Write-Output 'No saved private beta services.'
        } else {
            # Check all identities before stopping any service.
            foreach ($entry in @($state.backend_children)) { $null = Get-OwnedProcess $entry }
            foreach ($name in @('backend', 'tunnel')) { $null = Get-OwnedProcess $state.$name }
            if ($Action -eq 'stop') {
                foreach ($entry in @($state.backend_children)) { Stop-OwnedProcess $entry }
            }
            foreach ($name in @('backend', 'tunnel')) {
                $process = Get-OwnedProcess $state.$name
                if ($Action -eq 'stop') { Stop-OwnedProcess $state.$name }
                $serviceStatus = if ($process -and $Action -eq 'status') { 'running' } else { 'stopped' }
                Write-Output "$name`: $serviceStatus"
            }
            if ($Action -eq 'stop') {
                Remove-Item -LiteralPath $statePath
            } elseif ($state.origin) {
                Write-Output "Website: $($state.origin)/"
                Write-Output "Private files and logs: $runtimeRoot"
            }
        }
        return
    }

    if ($state) {
        foreach ($entry in @($state.backend_children)) {
            if (Get-OwnedProcess $entry) { throw 'A saved backend worker is running. Stop this beta before restarting.' }
        }
        foreach ($name in @('backend', 'tunnel')) {
            if (Get-OwnedProcess $state.$name) {
                throw "A saved $name process is running. Use -Action stop with the same -EnvFile first."
            }
        }
    }
    if (Get-PortListener $Port) {
        throw "Port $Port is occupied. No existing service was changed. Choose another port."
    }
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) { throw 'Prepare the private .env file first.' }
    if (-not (Test-Path -LiteralPath $tunnelExecutable -PathType Leaf)) {
        throw "Install cloudflared at $tunnelExecutable first."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $backendRoot 'config\private_beta.py') -PathType Leaf)) {
        throw 'The private beta backend entry point is missing.'
    }
    if (-not $PythonPath) {
        $PythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
            if (-not (Test-Path -LiteralPath $pythonPathFile -PathType Leaf)) {
                throw 'No project virtualenv or saved interpreter was found. Supply -PythonPath once.'
            }
            $PythonPath = [IO.File]::ReadAllText($pythonPathFile).Trim()
            if (-not [IO.Path]::IsPathRooted($PythonPath) -or
                -not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
                throw 'The saved interpreter is unavailable. Supply the verified virtualenv using -PythonPath.'
            }
        }
    }
    $pythonExecutable = (Get-Command $PythonPath -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    [IO.File]::WriteAllText($pythonPathFile, $pythonExecutable + "`r`n", (New-Object Text.UTF8Encoding($false)))
    if ($EnvFile.Contains('"')) { throw 'The environment path cannot contain a quote.' }
    $originalEnvironment = [IO.File]::ReadAllBytes($EnvFile)
    $state = @{ version = 1; env_file = $EnvFile; port = $Port; origin = $null; backend = $null; backend_children = @(); tunnel = $null }
    Save-State $state

    $target = "http://127.0.0.1:$Port"
    $tunnel = Start-Process -FilePath $tunnelExecutable -WorkingDirectory $runtimeRoot `
        -ArgumentList @('tunnel', '--url', $target, '--no-autoupdate', '--protocol', 'http2') `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput $tunnelOutput -RedirectStandardError $tunnelError
    $started += $tunnel
    $state.tunnel = New-ProcessEntry $tunnel @('tunnel', $target, '--protocol http2')
    Save-State $state
    $origin = $null
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($tunnel.HasExited) { throw "The tunnel exited. Check logs in $runtimeRoot" }
        foreach ($logPath in @($tunnelOutput, $tunnelError)) {
            if (Test-Path -LiteralPath $logPath) {
                $logText = Get-Content -LiteralPath $logPath -Raw -ErrorAction SilentlyContinue
                if ([string]::IsNullOrWhiteSpace($logText)) { continue }
                $found = [regex]::Match([string]$logText, 'https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\b')
                if ($found.Success) { $origin = $found.Value; break }
            }
        }
        if ($origin) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $origin) { throw "The tunnel did not provide a URL within 60 seconds. Check logs in $runtimeRoot" }
    # Detect another service winning the port race before exposing this backend.
    if (Get-PortListener $Port) { throw "Port $Port became occupied. The existing service will not be stopped." }
    Write-Origin $origin
    $originChanged = $true
    $state.origin = $origin
    Save-State $state
    $backend = Start-Process -FilePath $pythonExecutable -WorkingDirectory $backendRoot `
        -ArgumentList @('-m', 'config.private_beta', '--port', [string]$Port, '--env-file', ('"{0}"' -f $EnvFile)) `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeRoot 'backend.out.log') `
        -RedirectStandardError (Join-Path $runtimeRoot 'backend.err.log')
    $started += $backend
    $state.backend = New-ProcessEntry $backend @('config.private_beta', $EnvFile, "--port $Port")
    Save-State $state
    $ready = $false
    $backendReadyClock = [Diagnostics.Stopwatch]::StartNew()
    while ($backendReadyClock.Elapsed.TotalSeconds -lt 180) {
        Update-BackendChildren $state
        if ($backend.HasExited -or $tunnel.HasExited) {
            throw "A beta service exited during startup. Check logs in $runtimeRoot"
        }
        $listeners = Get-PortListener $Port
        if ($listeners.Count -gt 0) {
            $ownedIds = @($backend.Id) + @($state.backend_children | ForEach-Object { $_.id })
            if (@($listeners | Where-Object { $_.OwningProcess -notin $ownedIds }).Count -gt 0) {
                throw "Port $Port belongs to another process. It will not be stopped."
            }
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "The backend did not become ready within 180 seconds. Check logs in $runtimeRoot" }
    Update-InvitationOrigins $origin
    Write-Output "Website: $origin/"
    Write-Output "Private files and logs: $runtimeRoot"
    Write-Output 'Backend is listening; verify HTTPS and Basic authentication before sharing the URL.'
} catch {
    $startupError = $_
    if ($started.Count -gt 0) {
        $cleanupFailed = $false
        if ($state.backend) {
            try { Update-BackendChildren $state } catch { $cleanupFailed = $true }
        }
        foreach ($entry in @($state.backend_children)) {
            try { Stop-OwnedProcess $entry } catch { $cleanupFailed = $true }
        }
        foreach ($name in @('backend', 'tunnel')) {
            try { Stop-OwnedProcess $state.$name } catch { $cleanupFailed = $true }
        }
        # The Process object retains the identity of a just-started process even if
        # collecting its CIM metadata failed before a state entry could be written.
        foreach ($process in $started) {
            try { if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit(10000) | Out-Null } }
            catch { $cleanupFailed = $true }
        }
        if ($originChanged -and $null -ne $originalEnvironment) {
            [IO.File]::WriteAllBytes($EnvFile, $originalEnvironment)
        }
        if (-not $cleanupFailed -and (Test-Path -LiteralPath $statePath)) {
            Remove-Item -LiteralPath $statePath
        }
    }
    throw $startupError
} finally {
    if ($lock) { $lock.Dispose() }
}
