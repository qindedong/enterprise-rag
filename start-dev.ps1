# ============================================================
# RAG 知识库系统 — 开发模式一键启动 (Windows)
# ============================================================
# 用法:
#   .\start-dev.ps1          启动全部服务并打开浏览器
#   .\start-dev.ps1 -Stop    停止应用进程（保留数据库容器）
#   .\start-dev.ps1 -Status  查看服务状态
#
# 与 start.ps1 的区别:
#   start.ps1      生产模式 — 全部服务打包进 Docker（慢，适合部署）
#   start-dev.ps1  开发模式 — 本地 venv + Vite 热更新（快，适合日常用）
# ============================================================
param (
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"
$LogDir = Join-Path $Backend "logs"
$Containers = @("rag-postgres", "rag-qdrant", "rag-redis")

function Write-Success { Write-Host "✅ $args" -ForegroundColor Green }
function Write-ErrorMsg { Write-Host "❌ $args" -ForegroundColor Red }
function Write-Warning { Write-Host "⚠️  $args" -ForegroundColor Yellow }
function Write-Step { Write-Host ""; Write-Host "▶ $args" -ForegroundColor Cyan }
function Write-Info { Write-Host "   $args" -ForegroundColor Gray }

# Docker CLI：PATH 找不到时用 Docker Desktop 默认路径
function Get-Docker {
    if (Get-Command "docker" -ErrorAction SilentlyContinue) { return "docker" }
    $p = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $p) { return $p }
    return $null
}

function Test-PortBusy([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

# ===== -Status =====
if ($Status) {
    Write-Step "服务状态:"
    foreach ($c in $Containers) {
        $st = & (Get-Docker) inspect --format "{{.State.Status}}/{{.State.Health.Status}}" $c 2>$null
        Write-Info ("容器 {0,-15} {1}" -f $c, $(if ($st) { $st } else { "不存在" }))
    }
    Write-Info ("后端 API  :8000   " + $(if (Test-PortBusy 8000) { "运行中" } else { "未运行" }))
    Write-Info ("前端 Vite :3000   " + $(if (Test-PortBusy 3000) { "运行中" } else { "未运行" }))
    exit 0
}

# ===== -Stop =====
if ($Stop) {
    Write-Step "停止应用进程（保留数据库容器）..."
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'uvicorn|app\.worker' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Info "已停止 PID $($_.ProcessId)" }
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object { $_.CommandLine -match 'vite' -and $_.CommandLine -match [regex]::Escape($Frontend) } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Info "已停止前端 PID $($_.ProcessId)" }
    Write-Success "应用进程已停止（数据库容器仍在运行，docker stop 可手动停）"
    exit 0
}

# ===== 启动 =====
Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   企业知识库 RAG — 开发模式一键启动      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan

# 1. Docker 依赖容器
Write-Step "1/4 启动数据库容器..."
$Docker = Get-Docker
if (-not $Docker) { Write-ErrorMsg "未找到 Docker，请先安装 Docker Desktop"; exit 1 }
try { $null = & $Docker info 2>&1 } catch { Write-ErrorMsg "Docker Desktop 未运行，请先启动它"; exit 1 }

foreach ($c in $Containers) {
    $exists = & $Docker ps -a --format "{{.Names}}" | Select-String -SimpleMatch $c
    if ($exists) {
        $null = & $Docker start $c 2>&1
    } else {
        Write-ErrorMsg "容器 $c 不存在，请先运行 start.ps1 或手动创建"
        exit 1
    }
}
# 等待健康
$waited = 0
do {
    Start-Sleep -Seconds 2; $waited += 2
    $healthy = 0
    foreach ($c in $Containers) {
        $h = & $Docker inspect --format "{{.State.Health.Status}}" $c 2>$null
        if ($h -eq "healthy") { $healthy++ }
    }
} while ($healthy -lt $Containers.Count -and $waited -lt 60)
if ($healthy -lt $Containers.Count) { Write-ErrorMsg "容器健康检查超时"; exit 1 }
Write-Success "Postgres / Qdrant / Redis 全部健康"

# 2. 配置与虚拟环境检查
if (-not (Test-Path (Join-Path $Backend ".env"))) { Write-ErrorMsg "backend\.env 不存在"; exit 1 }
if (-not (Test-Path $VenvPy)) { Write-ErrorMsg "虚拟环境不存在: $VenvPy（先跑一次 backend 的 uv sync / pip install）"; exit 1 }
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# 3. 后端 API + Worker
Write-Step "2/4 启动后端 API (:8000) 和 Worker..."
if (Test-PortBusy 8000) {
    Write-Warning "8000 端口已被占用，跳过后端启动（视为已在运行）"
} else {
    Start-Process -FilePath $VenvPy -WindowStyle Hidden -WorkingDirectory $Backend `
        -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' `
        -RedirectStandardOutput "$LogDir\api.log" -RedirectStandardError "$LogDir\api.err.log"
}
$workerRunning = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'app\.worker' }
if ($workerRunning) {
    Write-Warning "Worker 已在运行，跳过"
} else {
    Start-Process -FilePath $VenvPy -WindowStyle Hidden -WorkingDirectory $Backend `
        -ArgumentList '-m','app.worker' `
        -RedirectStandardOutput "$LogDir\worker.log" -RedirectStandardError "$LogDir\worker.err.log"
}

# 等待 API 就绪
$waited = 0
do {
    Start-Sleep -Seconds 3; $waited += 3
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        $ok = ($r.status -eq "healthy")
    } catch { $ok = $false }
} while (-not $ok -and $waited -lt 90)
if (-not $ok) { Write-ErrorMsg "后端启动超时，查看 $LogDir\api.log"; exit 1 }
Write-Success "后端 API 就绪"

# 4. 前端 Vite (:3000，代理 /api → :8000)
Write-Step "3/4 启动前端开发服务器 (:3000)..."
if (Test-PortBusy 3000) {
    Write-Warning "3000 端口已被占用，跳过前端启动（视为已在运行）"
} else {
    $npm = (Get-Command "npm.cmd" -ErrorAction SilentlyContinue).Source
    if (-not $npm) { $npm = (Get-Command "npm" -ErrorAction SilentlyContinue).Source }
    if (-not $npm) { Write-ErrorMsg "未找到 npm，请先安装 Node.js"; exit 1 }
    # .cmd 不能直接被 Start-Process 带参数执行，经 cmd.exe 调起；
    # 用 /k 保持窗口承载子进程，日志由 PowerShell 重定向
    Start-Process -FilePath "cmd.exe" -WindowStyle Hidden -WorkingDirectory $Frontend `
        -ArgumentList '/c', "npm run dev" `
        -RedirectStandardOutput "$LogDir\vite.log" -RedirectStandardError "$LogDir\vite.err.log"
    $waited = 0
    do { Start-Sleep -Seconds 2; $waited += 2 } while (-not (Test-PortBusy 3000) -and $waited -lt 60)
    if (-not (Test-PortBusy 3000)) { Write-ErrorMsg "前端启动超时，查看 $LogDir\vite.log"; exit 1 }
}
Write-Success "前端就绪"

# 5. 打开浏览器
Write-Step "4/4 打开浏览器..."
Start-Process "http://localhost:3000/"

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║            🎉 启动完成！                 ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  前端页面:  http://localhost:3000        ║" -ForegroundColor Green
Write-Host "║  API 文档:  http://127.0.0.1:8000/docs   ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════╣" -ForegroundColor Gray
Write-Host "║  日志: backend\logs\ (api/worker/vite)   ║" -ForegroundColor Gray
Write-Host "║  停止: .\start-dev.ps1 -Stop             ║" -ForegroundColor Gray
Write-Host "║  状态: .\start-dev.ps1 -Status           ║" -ForegroundColor Gray
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Gray
