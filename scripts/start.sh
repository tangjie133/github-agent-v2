#!/bin/bash
#
# GitHub Agent V2 启动脚本
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

# 默认配置
HOST="${GITHUB_AGENT_HOST:-0.0.0.0}"
PORT="${GITHUB_AGENT_PORT:-8080}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# 打印信息
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    info "检查依赖..."
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        error "Python3 未安装"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    info "Python 版本: $PYTHON_VERSION"
    
    # 检查虚拟环境
    if [ ! -d "$VENV_DIR" ]; then
        warning "虚拟环境不存在，正在创建..."
        python3 -m venv "$VENV_DIR"
        success "虚拟环境创建完成"
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 检查并安装依赖
    if [ ! -f "$VENV_DIR/.dependencies_installed" ] || [ "$PROJECT_DIR/requirements.txt" -nt "$VENV_DIR/.dependencies_installed" ]; then
        info "安装依赖..."
        pip install -q --upgrade pip
        pip install -q -r "$PROJECT_DIR/requirements.txt"
        touch "$VENV_DIR/.dependencies_installed"
        success "依赖安装完成"
    fi
}

# 检查环境变量
check_env() {
    info "检查环境变量..."
    
    local missing=()
    
    if [ -z "$GITHUB_APP_ID" ]; then
        missing+=("GITHUB_APP_ID")
    fi
    
    if [ -z "$GITHUB_PRIVATE_KEY_PATH" ] && [ -z "$GITHUB_PRIVATE_KEY" ]; then
        missing+=("GITHUB_PRIVATE_KEY_PATH 或 GITHUB_PRIVATE_KEY")
    fi
    
    if [ -z "$GITHUB_WEBHOOK_SECRET" ]; then
        missing+=("GITHUB_WEBHOOK_SECRET")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        error "缺少必要的环境变量:"
        for var in "${missing[@]}"; do
            echo "  - $var"
        done
        echo ""
        info "请设置环境变量或创建 .env 文件"
        exit 1
    fi
    
    success "环境变量检查通过"
}

# 启动 KB Service
start_kb_service() {
    info "启动 KB Service (知识库服务)..."
    
    KB_HOST="${KB_SERVICE_HOST:-0.0.0.0}"
    KB_PORT="${KB_SERVICE_PORT:-8000}"
    KB_URL="http://$KB_HOST:$KB_PORT"
    
    # 检查是否已有 KB Service 在运行
    if curl -s "$KB_URL/health" > /dev/null 2>&1; then
        success "KB Service 已在运行 ($KB_URL)"
        return 0
    fi
    
    # 检查 nomic-embed-text 模型
    OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
    if ! curl -s "$OLLAMA_HOST/api/tags" | grep -q "nomic-embed-text"; then
        warning "nomic-embed-text 模型未找到，正在拉取..."
        info "运行: ollama pull nomic-embed-text"
        ollama pull nomic-embed-text || {
            error "拉取 nomic-embed-text 模型失败"
            return 1
        }
        success "nomic-embed-text 模型已就绪"
    fi
    
    # 后台启动 KB Service
    info "正在启动 KB Service $KB_HOST:$KB_PORT..."
    cd "$PROJECT_DIR"
    nohup python3 -m knowledge_base.kb_service --host "$KB_HOST" --port "$KB_PORT" > /tmp/kb_service.log 2>&1 &
    KB_PID=$!
    
    # 等待服务启动
    info "等待 KB Service 启动..."
    for i in {1..30}; do
        if curl -s "$KB_URL/health" > /dev/null 2>&1; then
            success "KB Service 启动成功 ($KB_URL)"
            return 0
        fi
        sleep 1
    done
    
    error "KB Service 启动超时"
    warning "查看日志: tail -f /tmp/kb_service.log"
    return 1
}

# 停止 KB Service
stop_kb_service() {
    info "停止 KB Service..."
    pkill -f "knowledge_base.kb_service" 2>/dev/null || true
}

# 检查是否需要 GitHub 知识库同步
is_github_kb_enabled() {
    [ "${KB_GITHUB_SYNC_ENABLED:-false}" == "true" ]
}

# 初始同步（前台执行，必须在 KB Service 之前）
sync_github_kb_if_enabled() {
    if ! is_github_kb_enabled; then
        info "GitHub 知识库同步未启用 (设置 KB_GITHUB_SYNC_ENABLED=true 启用)"
        return 0
    fi
    
    local repo="${KB_REPO:-tangjie133/knowledge-base}"
    local branch="${KB_BRANCH:-main}"
    
    info "=========================================="
    info "GitHub 知识库初始同步"
    info "=========================================="
    info "仓库: $repo"
    info "分支: $branch"
    info ""
    
    cd "$PROJECT_DIR"
    
    # 前台执行同步，等待完成
    if python3 scripts/github_repo_watcher.py --sync; then
        success "初始同步完成"
        
        # 统计同步的文件
        local md_count=$(find knowledge_base/chips knowledge_base/best_practices -name "*.md" 2>/dev/null | wc -l)
        info "知识库文档数: $md_count"
    else
        warning "初始同步失败或部分失败，继续启动..."
    fi
    
    info "=========================================="
}

# 启动后台同步和 Webhook（持续监控）
start_github_kb_daemon_if_enabled() {
    if ! is_github_kb_enabled; then
        return 0
    fi
    
    local sync_interval="${KB_SYNC_INTERVAL:-0}"
    local webhook_enabled="${KB_WEBHOOK_ENABLED:-false}"
    local webhook_port="${KB_WEBHOOK_PORT:-9000}"
    
    info "启动 GitHub 知识库后台监控..."
    
    # 如果启用了定时同步
    if [ "$sync_interval" -gt 0 ] 2>/dev/null; then
        info "启动定时同步 (间隔: ${sync_interval}秒)..."
        nohup python3 scripts/github_repo_watcher.py --daemon --interval "$sync_interval" > /tmp/github_kb_sync.log 2>&1 &
        success "定时同步已启动 (PID: $!)"
    fi
    
    # 如果启用了 Webhook
    if [ "$webhook_enabled" == "true" ]; then
        info "启动 Webhook 接收服务器 (端口: $webhook_port)..."
        nohup python3 scripts/github_webhook_server.py --port "$webhook_port" > /tmp/github_webhook.log 2>&1 &
        success "Webhook 服务器已启动 (http://0.0.0.0:$webhook_port)"
        echo ""
        warning "记得在 GitHub 仓库设置 Webhook:"
        echo "  URL: http://$(hostname -I | awk '{print $1}'):$webhook_port/webhook"
        echo "  Secret: ${KB_WEBHOOK_SECRET:-'(未设置)'}"
    fi
    
    success "GitHub 知识库后台监控已启动"
}

# 停止 GitHub 知识库同步
stop_github_kb_sync() {
    info "停止 GitHub 知识库同步..."
    pkill -f "github_repo_watcher" 2>/dev/null || true
    pkill -f "github_webhook_server" 2>/dev/null || true
}

# 检查服务健康状态
check_services() {
    info "检查依赖服务..."
    
    # 检查 Ollama
    OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        success "Ollama 服务正常"
    else
        warning "Ollama 服务未启动或无法访问 ($OLLAMA_HOST)"
    fi
    
    # 检查 OpenClaw (可选)
    OPENCLAW_URL="${OPENCLAW_URL:-http://localhost:3000}"
    if curl -s "$OPENCLAW_URL/health" > /dev/null 2>&1; then
        success "OpenClaw 服务正常"
    else
        warning "OpenClaw 服务未启动或无法访问 ($OPENCLAW_URL) - 可选"
    fi
    
    # KB Service 由 start_kb_service 启动并检查
}

# 显示配置
show_config() {
    info "当前配置:"
    echo "  主机: $HOST"
    echo "  端口: $PORT"
    echo "  日志级别: $LOG_LEVEL"
    echo "  工作目录: ${GITHUB_AGENT_WORKDIR:-/tmp/github-agent-v2}"
    echo "  Issue 触发模式: ${GITHUB_AGENT_ISSUE_TRIGGER_MODE:-smart}"
    echo "  评论触发模式: ${GITHUB_AGENT_COMMENT_TRIGGER_MODE:-smart}"
    echo "  确认模式: ${AGENT_CONFIRM_MODE:-auto}"
    
    # GitHub KB 同步配置
    local kb_sync="${KB_GITHUB_SYNC_ENABLED:-false}"
    if [ "$kb_sync" == "true" ]; then
        echo ""
        echo "  GitHub 知识库同步:"
        echo "    仓库: ${KB_REPO:-tangjie133/knowledge-base}"
        echo "    分支: ${KB_BRANCH:-main}"
        echo "    Webhook: ${KB_WEBHOOK_ENABLED:-false}"
        [ "${KB_SYNC_INTERVAL:-0}" -gt 0 ] 2>/dev/null && echo "    同步间隔: ${KB_SYNC_INTERVAL}秒"
    fi
}

# 启动服务
start_server() {
    info "启动 GitHub Agent V2..."
    
    cd "$PROJECT_DIR"
    
    # 设置 PYTHONPATH
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
    
    success "服务启动中..."
    echo ""
    echo "=================================="
    echo "GitHub Agent V2 正在运行"
    echo "监听地址: http://$HOST:$PORT"
    echo "按 Ctrl+C 停止服务"
    echo "=================================="
    echo ""
    
    # 启动服务
    exec python3 main.py --host "$HOST" --port "$PORT"
}

# 主函数
main() {
    echo "=================================="
    echo "  GitHub Agent V2 启动脚本"
    echo "=================================="
    echo ""
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host)
                HOST="$2"
                shift 2
                ;;
            --port)
                PORT="$2"
                shift 2
                ;;
            --log-level)
                LOG_LEVEL="$2"
                shift 2
                ;;
            --skip-health-check)
                SKIP_HEALTH_CHECK=1
                shift
                ;;
            --help)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  --host <host>           监听主机 (默认: 0.0.0.0)"
                echo "  --port <port>           监听端口 (默认: 8080)"
                echo "  --log-level <level>     日志级别 (默认: INFO)"
                echo "  --skip-health-check     跳过服务健康检查"
                echo "  --help                  显示帮助"
                echo ""
                echo "GitHub 知识库同步配置 (.env):"
                echo "  KB_GITHUB_SYNC_ENABLED  启用同步 (true/false)"
                echo "  KB_REPO                 仓库地址 (owner/repo)"
                echo "  KB_BRANCH               分支名称"
                echo "  KB_SYNC_INTERVAL        同步间隔(秒)，0为不同步"
                echo "  KB_WEBHOOK_ENABLED      启用Webhook (true/false)"
                exit 0
                ;;
            *)
                error "未知选项: $1"
                exit 1
                ;;
        esac
    done
    
    # 执行步骤
    check_dependencies
    check_env
    
    # 步骤1: GitHub 知识库同步（先同步文件到本地）
    # 必须在 KB Service 之前，确保向量库加载最新文档
    sync_github_kb_if_enabled
    
    # 步骤2: 启动 KB Service（加载本地文档到向量库）
    start_kb_service
    
    # 步骤3: 启动后台同步和 Webhook（持续监控更新）
    start_github_kb_daemon_if_enabled
    
    if [ -z "$SKIP_HEALTH_CHECK" ]; then
        check_services
    fi
    
    show_config
    start_server
}

# 捕获中断信号，确保停止所有服务
trap 'info "正在停止服务..."; stop_github_kb_sync; stop_kb_service; exit 0' INT TERM EXIT

# 运行主函数
main "$@"
