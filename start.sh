#!/usr/bin/env bash
# ============================================================
# RAG 知识库系统 — Linux/Mac 一键启动脚本
# ============================================================
# 用法:
#   ./start.sh                 启动（增量构建）
#   ./start.sh --build         强制重新构建
#   ./start.sh --down          停止并清理所有服务
#   ./start.sh --logs          查看所有服务日志
#   ./start.sh --status        查看服务运行状态
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.prod.yml"

# ===== 终端颜色 =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # 无颜色

success() { echo -e "${GREEN}✅ $*${NC}"; }
error()   { echo -e "${RED}❌ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠️  $*${NC}"; }
step()    { echo ""; echo -e "${CYAN}▶ $*${NC}"; }
info()    { echo -e "${GRAY}   $*${NC}"; }

# ===== 打印横幅 =====
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗"
echo -e "${CYAN}║     企业级知识库 RAG — 一键部署 (Linux/Mac)     ║"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"

# ===== 检查前置条件 =====
step "检查运行环境..."

if ! command -v docker &> /dev/null; then
    error "未找到 Docker，请先安装 Docker"
    info "Linux: https://docs.docker.com/engine/install/"
    info "Mac:   https://docs.docker.com/desktop/install/mac-install/"
    exit 1
fi
success "Docker 已安装"

# 检查 Docker 是否运行
if ! docker info &> /dev/null; then
    error "Docker 未运行，请先启动 Docker"
    exit 1
fi
success "Docker 正在运行"

# 检测 docker compose 命令（新版 Docker 用子命令，旧版用 docker-compose）
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    warn "使用旧版 docker-compose，建议升级到 Docker Compose v2"
else
    error "未找到 docker compose 命令"
    exit 1
fi

# ===== 查看状态 =====
if [[ "${1:-}" == "--status" ]]; then
    step "服务运行状态:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps
    exit 0
fi

# ===== 查看日志 =====
if [[ "${1:-}" == "--logs" ]]; then
    step "查看服务日志 (Ctrl+C 退出):"
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f
    exit 0
fi

# ===== 停止服务 =====
if [[ "${1:-}" == "--down" ]]; then
    step "停止所有服务..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" down
    success "所有服务已停止"
    exit 0
fi

# ===== 检查环境变量 =====
step "检查配置文件..."
if [ ! -f backend/.env ]; then
    if [ -f backend/.env.template ]; then
        warn "backend/.env 不存在，正在从模板创建..."
        cp backend/.env.template backend/.env
        warn "请先编辑 backend/.env，填写必要的配置后重新运行此脚本"
        info "必须填写的配置: LLM_API_KEY、JWT_SECRET_KEY"
        exit 1
    else
        error "backend/.env.template 不存在，无法创建配置"
        exit 1
    fi
fi
success "配置文件已就绪"

# ===== 构建镜像 =====
step "构建 Docker 镜像..."
if [[ "${1:-}" == "--build" ]]; then
    info "强制重新构建所有镜像（--no-cache）..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache
else
    info "增量构建（仅构建变更部分）..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" build
fi

if [ $? -ne 0 ]; then
    error "镜像构建失败，请检查上方错误信息"
    exit 1
fi
success "镜像构建完成"

# ===== 启动服务 =====
step "启动所有服务..."
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d

if [ $? -ne 0 ]; then
    error "服务启动失败"
    exit 1
fi

# ===== 等待服务就绪 =====
step "等待服务就绪（约 15 秒）..."
info "首次启动需要初始化数据库，请耐心等待..."
max_wait=60
waited=0
while [ $waited -lt $max_wait ]; do
    sleep 3
    waited=$((waited + 3))

    # 检查后端 API
    if api_resp=$(curl -s http://localhost/health 2>/dev/null); then
        api_status=$(echo "$api_resp" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        success "后端 API 已就绪 (状态: ${api_status:-ok})"
        break
    else
        info "等待后端启动... (${waited}秒)"
    fi
done

if [ $waited -ge $max_wait ]; then
    warn "后端启动超时，请检查日志: $COMPOSE_CMD -f $COMPOSE_FILE logs api"
fi

# ===== 最终状态 =====
step "服务运行状态:"
$COMPOSE_CMD -f "$COMPOSE_FILE" ps

# ===== 打印访问信息 =====
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗"
echo -e "${GREEN}║               🎉 部署完成！                      ║"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣"
echo -e "${GREEN}║  前端页面:   http://localhost                   ║"
echo -e "${GREEN}║  API 文档:   http://localhost/docs              ║"
echo -e "${GREEN}║  健康检查:   http://localhost/health            ║"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${GRAY}"
echo -e "║  常用命令:                                       "
echo -e "║    ./start.sh --status   查看服务状态             "
echo -e "║    ./start.sh --logs     查看服务日志             "
echo -e "║    ./start.sh --down     停止所有服务             "
echo -e "║    ./start.sh --build    强制重建并启动           "
echo -e "${GRAY}╚══════════════════════════════════════════════════╝${NC}"
