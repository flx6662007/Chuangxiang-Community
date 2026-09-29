param([ValidateSet('ingest', 'settle')][string]$Task = 'ingest')
# Manual entry point. Scheduled tasks invoke pythonw.exe directly.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pythonPath = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
$runner = Join-Path $PSScriptRoot 'run-maintenance.py'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create backend/.venv and install its dependencies first.' }
& $pythonPath $runner --task $Task
exit $LASTEXITCODE
