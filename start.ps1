# ============================================================
# RAG 知识库系统 — Windows 一键启动脚本
# ============================================================
# 用法:
#   .\start.ps1                启动（增量构建）
#   .\start.ps1 -Build         强制重新构建
#   .\start.ps1 -Down          停止并清理所有服务
#   .\start.ps1 -Logs          查看所有服务日志
#   .\start.ps1 -Status        查看服务运行状态
# ============================================================
param (
    [switch]$Build,
    [switch]$Down,
    [switch]$Logs,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ===== 终端颜色辅助函数 =====
function Write-Success { Write-Host "✅ $args" -ForegroundColor Green }
function Write-ErrorMsg { Write-Host "❌ $args" -ForegroundColor Red }
function Write-Warning { Write-Host "⚠️  $args" -ForegroundColor Yellow }
function Write-Step    { Write-Host ""; Write-Host "▶ $args" -ForegroundColor Cyan }
function Write-Info    { Write-Host "   $args" -ForegroundColor Gray }

# ===== 打印横幅 =====
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     企业级知识库 RAG — 一键部署 (Windows)       ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan

# ===== 检查环境 =====
Write-Step "检查运行环境..."

# 检查 Docker
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-ErrorMsg "未找到 Docker，请先安装 Docker Desktop"
    Write-Info "下载地址: https://www.docker.com/products/docker-desktop"
    exit 1
}
Write-Success "Docker 已安装"

# 检查 Docker 是否在运行
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Docker 未运行，请先启动 Docker Desktop"
        exit 1
    }
} catch {
    Write-ErrorMsg "Docker 未运行，请先启动 Docker Desktop"
    exit 1
}
Write-Success "Docker 正在运行"

# 确定 compose 命令（新版: docker compose, 旧版: docker-compose）
try {
    $null = docker compose version 2>&1
} catch {
    if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
        $ComposeExe = "docker-compose"
        Write-Warning "使用旧版 docker-compose，建议升级 Docker"
    } else {
        Write-ErrorMsg "未找到 docker compose 命令"
        exit 1
    }
}

# 构建 compose 命令的便捷函数
function Invoke-Compose {
    if ($ComposeExe) {
        & $ComposeExe @args
    } else {
        & docker compose @args
    }
}

# ===== /status =====
if ($Status) {
    Write-Step "服务运行状态:"
    Invoke-Compose -f docker-compose.prod.yml ps
    exit 0
}

# ===== /logs =====
if ($Logs) {
    Write-Step "查看服务日志 (Ctrl+C 退出):"
    Invoke-Compose -f docker-compose.prod.yml logs -f
    exit 0
}

# ===== /down =====
if ($Down) {
    Write-Step "停止所有服务..."
    Invoke-Compose -f docker-compose.prod.yml down
    Write-Success "所有服务已停止"
    exit 0
}

# ===== 检查 .env =====
Write-Step "检查配置文件..."
if (-not (Test-Path "backend\.env")) {
    if (Test-Path "backend\.env.template") {
        Write-Warning "backend\.env 不存在，正在从模板创建..."
        Copy-Item "backend\.env.template" "backend\.env"
        Write-Warning "请先编辑 backend\.env，填写必要的配置后重新运行此脚本"
        Write-Info "必须填写的配置: LLM_API_KEY、JWT_SECRET_KEY"
        exit 1
    } else {
        Write-ErrorMsg "backend\.env.template 不存在，无法创建配置"
        exit 1
    }
}
Write-Success "配置文件已就绪"

# ===== 构建 =====
Write-Step "构建 Docker 镜像..."
if ($Build) {
    Write-Info "强制重新构建所有镜像（--no-cache）..."
    Invoke-Compose -f docker-compose.prod.yml build --no-cache
} else {
    Write-Info "增量构建（仅构建变更部分）..."
    Invoke-Compose -f docker-compose.prod.yml build
}

if ($LASTEXITCODE -ne 0) {
    Write-ErrorMsg "镜像构建失败，请检查上方错误信息"
    exit 1
}
Write-Success "镜像构建完成"

# ===== 启动 =====
Write-Step "启动所有服务..."
Invoke-Compose -f docker-compose.prod.yml up -d

if ($LASTEXITCODE -ne 0) {
    Write-ErrorMsg "服务启动失败"
    exit 1
}

# ===== 等待就绪 =====
Write-Step "等待服务就绪（约 15 秒）..."
Write-Info "首次启动需要下载镜像 + 初始化数据库，请耐心等待..."
$maxWait = 90
$waited = 0
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 3
    $waited += 3

    try {
        $apiResp = Invoke-RestMethod -Uri "http://localhost/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($apiResp) {
            Write-Success "后端 API 已就绪 (状态: $($apiResp.status))"
            break
        }
    } catch {
        Write-Info "等待后端启动... ($waited 秒)"
    }
}

if ($waited -ge $maxWait) {
    Write-Warning "后端启动超时，请检查日志: docker compose -f docker-compose.prod.yml logs api"
}

# ===== 状态 =====
Write-Step "服务运行状态:"
Invoke-Compose -f docker-compose.prod.yml ps

# ===== 完成 =====
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║               🎉 部署完成！                      ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  前端页面:   http://localhost                   ║" -ForegroundColor Green
Write-Host "║  API 文档:   http://localhost/docs              ║" -ForegroundColor Green
Write-Host "║  健康检查:   http://localhost/health            ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════╣" -ForegroundColor Gray
Write-Host "║  常用命令:                                       " -ForegroundColor Gray
Write-Host "║    .\start.ps1 -Status   查看服务状态             " -ForegroundColor Gray
Write-Host "║    .\start.ps1 -Logs     查看服务日志             " -ForegroundColor Gray
Write-Host "║    .\start.ps1 -Down     停止所有服务             " -ForegroundColor Gray
Write-Host "║    .\start.ps1 -Build    强制重建并启动           " -ForegroundColor Gray
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Gray
