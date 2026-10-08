# Start only the optional local search service; do not modify backend/.env.
$ErrorActionPreference = 'Stop'
$searchDockerBin = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath (Join-Path $searchDockerBin 'docker.exe'))) {
    $env:PATH = "$searchDockerBin;$env:PATH"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw '请先安装并启动 Docker Desktop（Linux containers），再重新运行此脚本。'
}
$searchRoot = Split-Path -Parent $PSScriptRoot
$searchSettings = Join-Path $searchRoot 'deploy\searxng\settings.yml'
$searchName = 'chuangxiang-search'
& docker info --format '{{.OSType}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker 服务未就绪，请先启动 Docker Desktop。' }
$searchExisting = & docker container ls -a --filter "name=^/$searchName`$" --format '{{.Names}}'
if ($LASTEXITCODE -ne 0) { throw '无法读取 Docker 容器列表。' }
if ($searchExisting -eq $searchName) {
    Write-Output '该名称的容器已存在；未重建或修改。可用 docker start chuangxiang-search 启动。'
    exit 0
}
$searchBytes = New-Object byte[] 32
$searchRng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $searchRng.GetBytes($searchBytes) } finally { $searchRng.Dispose() }
$searchSecret = ([System.BitConverter]::ToString($searchBytes)).Replace('-', '').ToLowerInvariant()
& docker run --detach --name $searchName --restart unless-stopped --publish '127.0.0.1:8888:8080' `
    --env "SEARXNG_SECRET=$searchSecret" `
    --mount "type=bind,source=$searchSettings,target=/etc/searxng/settings.yml,readonly" `
    docker.io/searxng/searxng:latest
if ($LASTEXITCODE -ne 0) { throw 'SearXNG 启动失败，请查看上方 Docker 错误。' }
Write-Output 'SearXNG 已创建。待服务就绪后，在 backend/.env 设置 AI_SEARXNG_URL=http://127.0.0.1:8888 并重启后端。'
