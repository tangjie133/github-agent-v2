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
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# 项目目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

# 加载 .env 文件
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

# 设置代理（如果配置了）
if [ -n "$HTTP_PROXY" ]; then
    export http_proxy="$HTTP_PROXY"
    export HTTP_PROXY="$HTTP_PROXY"
fi
if [ -n "$HTTPS_PROXY" ]; then
    export https_proxy="$HTTPS_PROXY"
    export HTTPS_PROXY="$HTTPS_PROXY"
fi
if [ -n "$ALL_PROXY" ]; then
    export all_proxy="$ALL_PROXY"
    export ALL_PROXY="$ALL_PROXY"
fi

# 默认配置
HOST="${GITHUB_AGENT_HOST:-0.0.0.0}"
PORT="${GITHUB_AGENT_PORT:-8080}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# 打印信息
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
}

step() {
    echo -e "\n${CYAN}${BOLD}▶ $1${NC}"
}

# 显示 Banner
show_banner() {
    echo ""
    echo -e "${MAGENTA}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}${BOLD}║${NC}            ${CYAN}${BOLD}GitHub Agent V2${NC} - 智能 Issue 处理系统           ${MAGENTA}${BOLD}║${NC}"
    echo -e "${MAGENTA}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# 检查依赖
check_dependencies() {
    step "步骤 1/6: 检查环境依赖"
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        error "Python3 未安装"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    info "Python 版本: ${BOLD}$PYTHON_VERSION${NC}"
    
    # 检查虚拟环境
    if [ ! -d "$VENV_DIR" ]; then
        warning "虚拟环境不存在，正在创建..."
        python3 -m venv "$VENV_DIR"
        success "虚拟环境创建完成"
    else
        info "虚拟环境: ${BOLD}$VENV_DIR${NC}"
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 检查并安装依赖
    if [ ! -f "$VENV_DIR/.dependencies_installed" ] || [ "$PROJECT_DIR/requirements.txt" -nt "$VENV_DIR/.dependencies_installed" ]; then
        info "安装/更新依赖..."
        pip install -q --upgrade pip
        pip install -q -r "$PROJECT_DIR/requirements.txt"
        touch "$VENV_DIR/.dependencies_installed"
        success "依赖安装完成"
    else
        success "依赖已安装"
    fi
    
    # 检查 Ollama
    OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        OLLAMA_MODELS=$(curl -s "$OLLAMA_HOST/api/tags" | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join([m['name'] for m in d.get('models',[])][:3]))" 2>/dev/null || echo "unknown")
        success "Ollama 服务正常 (${OLLAMA_MODELS})"
    else
        warning "Ollama 服务未启动 (${OLLAMA_HOST})"
    fi
    
    echo ""
}

# 检查环境变量
check_env() {
    step "步骤 2/6: 检查配置"
    
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
            echo "    - $var"
        done
        echo ""
        info "请设置环境变量或创建 .env 文件"
        exit 1
    fi
    
    # 显示配置摘要
    echo "  ${BOLD}GitHub App:${NC}"
    echo "    App ID: ${GITHUB_APP_ID}"
    echo "    Webhook Secret: ${GITHUB_WEBHOOK_SECRET:0:3}***"
    
    echo ""
    echo "  ${BOLD}触发模式:${NC}"
    echo "    Issue: ${GITHUB_AGENT_ISSUE_TRIGGER_MODE:-smart}"
    echo "    评论: ${GITHUB_AGENT_COMMENT_TRIGGER_MODE:-smart}"
    echo "    确认模式: ${AGENT_CONFIRM_MODE:-auto}"
    
    # 代理状态
    if [ -n "$http_proxy" ]; then
        echo ""
        echo "  ${BOLD}代理配置:${NC}"
        echo "    HTTP: ${http_proxy}"
        [ -n "$https_proxy" ] && echo "    HTTPS: ${https_proxy}"
    fi
    
    success "配置检查通过"
    echo ""
}

# 显示知识库状态
show_kb_status() {
    local kb_url="${KB_SERVICE_URL:-http://localhost:8000}"
    
    if curl -s "$kb_url/health" > /dev/null 2>&1; then
        local stats=$(curl -s "$kb_url/stats" 2>/dev/null)
        local doc_count=$(echo "$stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_documents',0))" 2>/dev/null || echo "0")
        local model=$(echo "$stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('embedding_model','unknown'))" 2>/dev/null || echo "unknown")
        
        success "知识库服务正常"
        echo "    文档数: ${BOLD}$doc_count${NC}"
        echo "    嵌入模型: $model"
        
        # 列出知识库文件
        local md_count=$(find "$PROJECT_DIR/knowledge_base" -name "*.md" 2>/dev/null | wc -l)
        if [ "$md_count" -gt 0 ]; then
            echo "    本地文件: ${md_count} 个 Markdown"
        fi
    else
        warning "知识库服务未就绪"
    fi
}

# 启动 KB Service
start_kb_service() {
    step "步骤 4/6: 启动知识库服务"
    
    KB_HOST="${KB_SERVICE_HOST:-0.0.0.0}"
    KB_PORT="${KB_SERVICE_PORT:-8000}"
    KB_URL="http://$KB_HOST:$KB_PORT"
    
    # 检查是否已有 KB Service 在运行
    if curl -s "$KB_URL/health" > /dev/null 2>&1; then
        success "KB Service 已在运行 ($KB_URL)"
        show_kb_status
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
    
    # 后台启动 KB Service（使用 setsid 确保进程组分离）
    info "正在启动 KB Service $KB_HOST:$KB_PORT..."
    cd "$PROJECT_DIR"
    
    # 使用 setsid 创建新的会话，确保进程在后台持续运行
    setsid python3 -m knowledge_base.kb_service --host "$KB_HOST" --port "$KB_PORT" > /tmp/kb_service.log 2>&1 &
    KB_PID=$!
    
    # 等待服务启动
    info "等待 KB Service 启动..."
    local started=false
    for i in {1..30}; do
        if curl -s "$KB_URL/health" > /dev/null 2>&1; then
            started=true
            break
        fi
        sleep 1
    done
    
    if [ "$started" = true ]; then
        success "KB Service 启动成功"
        show_kb_status
        
        # 保存 PID 到文件（方便后续管理）
        echo $KB_PID > /tmp/kb_service.pid
        return 0
    else
        error "KB Service 启动超时"
        warning "查看日志: tail -f /tmp/kb_service.log"
        return 1
    fi
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

# 检查 GitHub Token
check_github_token() {
    if [ -z "$GITHUB_TOKEN" ]; then
        warning "GITHUB_TOKEN 未设置"
        info "GitHub API 有速率限制:"
        info "  - 未认证: 60 次请求/小时"
        info "  - 已认证: 5000 次请求/小时"
        info "建议设置 GITHUB_TOKEN 以避免同步失败"
        info "获取方式: https://github.com/settings/tokens"
        echo ""
        return 1
    else
        success "GITHUB_TOKEN 已设置"
        return 0
    fi
}

# 初始同步（前台执行，必须在 KB Service 之前）
sync_github_kb_if_enabled() {
    step "步骤 3/6: 同步 GitHub 知识库"
    
    if ! is_github_kb_enabled; then
        warning "GitHub 知识库同步未启用"
        info "设置 KB_GITHUB_SYNC_ENABLED=true 以启用"
        echo ""
        return 0
    fi
    
    # 检查 GitHub Token
    check_github_token
    
    local repo="${KB_REPO:-tangjie133/knowledge-base}"
    local branch="${KB_BRANCH:-main}"
    
    info "仓库: ${BOLD}$repo${NC}"
    info "分支: ${BOLD}$branch${NC}"
    [ -n "$http_proxy" ] && info "使用代理: ${http_proxy}"
    
    cd "$PROJECT_DIR"
    
    # 前台执行同步，等待完成
    info "正在同步..."
    if python3 scripts/github_repo_watcher.py --sync; then
        success "同步完成"
        
        # 统计同步的文件
        local md_count=$(find knowledge_base/chips knowledge_base/best_practices -name "*.md" 2>/dev/null | wc -l)
        local pdf_count=$(find knowledge_base/chips knowledge_base/best_practices -name "*.pdf" 2>/dev/null | wc -l)
        
        echo ""
        echo "  同步结果:"
        echo "    Markdown 文件: $md_count"
        [ "$pdf_count" -gt 0 ] && echo "    PDF 文件: $pdf_count"
    else
        warning "同步失败或部分失败"
        info "将继续启动，知识库可能不完整"
    fi
    
    echo ""
}

# 后台进程 PID 文件
WATCHER_PID_FILE="/tmp/github_repo_watcher.pid"
WEBHOOK_PID_FILE="/tmp/github_webhook_server.pid"

# 启动后台同步和 Webhook（持续监控）
start_github_kb_daemon_if_enabled() {
    if ! is_github_kb_enabled; then
        return 0
    fi
    
    local sync_interval="${KB_SYNC_INTERVAL:-0}"
    local webhook_enabled="${KB_WEBHOOK_ENABLED:-false}"
    local webhook_port="${KB_WEBHOOK_PORT:-9000}"
    
    info "启动后台监控..."
    
    # 如果启用了定时同步
    if [ "$sync_interval" -gt 0 ] 2>/dev/null; then
        info "定时同步: 每 ${sync_interval} 秒"
        nohup python3 scripts/github_repo_watcher.py --daemon --interval "$sync_interval" > /tmp/github_kb_sync.log 2>&1 &
        WATCHER_PID=$!
        echo $WATCHER_PID > "$WATCHER_PID_FILE"
        success "定时同步已启动 (PID: $WATCHER_PID)"
    fi
    
    # 如果启用了 Webhook
    if [ "$webhook_enabled" == "true" ]; then
        info "Webhook 服务器: http://0.0.0.0:$webhook_port"
        nohup python3 scripts/github_webhook_server.py --port "$webhook_port" > /tmp/github_webhook.log 2>&1 &
        WEBHOOK_PID=$!
        echo $WEBHOOK_PID > "$WEBHOOK_PID_FILE"
        success "Webhook 服务器已启动 (PID: $WEBHOOK_PID)"
        
        # 获取本机 IP
        local ip=$(hostname -I | awk '{print $1}')
        echo ""
        echo -e "  ${YELLOW}提示: 在 GitHub 仓库设置 Webhook${NC}"
        echo "    Payload URL: http://$ip:$webhook_port/webhook"
        echo "    Secret: ${KB_WEBHOOK_SECRET:-'(未设置)'}"
        echo "    事件: Just the push event"
    fi
    
    echo ""
}

# 停止 GitHub 知识库同步
stop_github_kb_sync() {
    info "停止 GitHub 知识库同步..."
    
    # 停止定时同步进程
    if [ -f "$WATCHER_PID_FILE" ]; then
        local watcher_pid=$(cat "$WATCHER_PID_FILE" 2>/dev/null)
        if [ -n "$watcher_pid" ] && kill -0 "$watcher_pid" 2>/dev/null; then
            kill -TERM "$watcher_pid" 2>/dev/null || true
            sleep 1
            # 强制终止如果还在运行
            if kill -0 "$watcher_pid" 2>/dev/null; then
                kill -KILL "$watcher_pid" 2>/dev/null || true
            fi
        fi
        rm -f "$WATCHER_PID_FILE"
    fi
    
    # 停止 Webhook 服务器
    if [ -f "$WEBHOOK_PID_FILE" ]; then
        local webhook_pid=$(cat "$WEBHOOK_PID_FILE" 2>/dev/null)
        if [ -n "$webhook_pid" ] && kill -0 "$webhook_pid" 2>/dev/null; then
            kill -TERM "$webhook_pid" 2>/dev/null || true
            sleep 1
            # 强制终止如果还在运行
            if kill -0 "$webhook_pid" 2>/dev/null; then
                kill -KILL "$webhook_pid" 2>/dev/null || true
            fi
        fi
        rm -f "$WEBHOOK_PID_FILE"
    fi
    
    # 备用：pkill 确保所有相关进程都被停止
    pkill -f "github_repo_watcher" 2>/dev/null || true
    pkill -f "github_webhook_server" 2>/dev/null || true
}

# 显示最终状态摘要
show_status_summary() {
    step "步骤 6/6: 启动主服务"
    
    local kb_url="${KB_SERVICE_URL:-http://localhost:8000}"
    local ollama_host="${OLLAMA_HOST:-http://localhost:11434}"
    
    echo ""
    echo -e "${GREEN}${BOLD}┌─────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${GREEN}${BOLD}│${NC}                      服务启动就绪                            ${GREEN}${BOLD}│${NC}"
    echo -e "${GREEN}${BOLD}└─────────────────────────────────────────────────────────────┘${NC}"
    echo ""
    
    # 服务状态表格
    echo -e "  ${BOLD}服务状态:${NC}"
    echo "  ┌────────────────────┬────────────────────────────────────────┐"
    
    # Ollama
    if curl -s "$ollama_host/api/tags" > /dev/null 2>&1; then
        echo -e "  │ ${GREEN}✓${NC} Ollama          │ $ollama_host                    │"
    else
        echo -e "  │ ${RED}✗${NC} Ollama          │ $ollama_host (未连接)            │"
    fi
    
    # KB Service
    if curl -s "$kb_url/stats" > /dev/null 2>&1; then
        local doc_count=$(curl -s "$kb_url/stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_documents',0))" 2>/dev/null)
        echo -e "  │ ${GREEN}✓${NC} 知识库服务      │ $kb_url (${doc_count} 文档)           │"
    else
        echo -e "  │ ${RED}✗${NC} 知识库服务      │ $kb_url (未启动)                  │"
    fi
    
    # GitHub KB 同步
    if is_github_kb_enabled; then
        echo -e "  │ ${GREEN}✓${NC} GitHub 同步     │ ${KB_REPO:-tangjie133/knowledge-base} │"
    else
        echo -e "  │ ${YELLOW}!${NC} GitHub 同步     │ 未启用                              │"
    fi
    
    echo "  └────────────────────┴────────────────────────────────────────┘"
    
    # 访问地址
    echo ""
    echo -e "  ${BOLD}访问地址:${NC}"
    echo "  ┌─────────────────────────────────────────────────────────────┐"
    echo -e "  │  ${CYAN}主服务${NC}        http://${HOST}:${PORT}                      │"
    echo -e "  │  ${CYAN}健康检查${NC}      http://${HOST}:${PORT}/health                │"
    echo -e "  │  ${CYAN}Webhook${NC}       http://${HOST}:${PORT}/webhook/github        │"
    echo -e "  │  ${CYAN}知识库 API${NC}    ${KB_SERVICE_URL:-http://localhost:8000}                   │"
    echo "  └─────────────────────────────────────────────────────────────┘"
    
    # 使用提示
    echo ""
    echo -e "  ${BOLD}使用提示:${NC}"
    echo "  • 在 Issue 中提及 @agent 来触发处理"
    echo "  • 按 Ctrl+C 停止所有服务"
    echo "  • 查看日志: tail -f /tmp/kb_service.log"
    echo ""
}

# 启动服务
start_server() {
    cd "$PROJECT_DIR"
    
    # 设置 PYTHONPATH
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
    
    # 启动服务
    exec python3 main.py --host "$HOST" --port "$PORT"
}

# 主函数
main() {
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
                echo "环境变量配置 (.env):"
                echo "  GITHUB_APP_ID           GitHub App ID (必需)"
                echo "  GITHUB_PRIVATE_KEY_PATH 私钥路径 (必需)"
                echo "  GITHUB_WEBHOOK_SECRET   Webhook Secret (必需)"
                echo "  KB_GITHUB_SYNC_ENABLED  启用知识库同步 (true/false)"
                echo "  KB_REPO                 知识库仓库 (owner/repo)"
                echo "  HTTP_PROXY              HTTP 代理地址"
                echo "  HTTPS_PROXY             HTTPS 代理地址"
                exit 0
                ;;
            *)
                error "未知选项: $1"
                exit 1
                ;;
        esac
    done
    
    # 显示 Banner
    show_banner
    
    # 执行步骤
    check_dependencies
    check_env
    sync_github_kb_if_enabled
    start_kb_service
    start_github_kb_daemon_if_enabled
    
    # 显示状态摘要
    show_status_summary
    
    # 启动主服务
    start_server
}

# 捕获中断信号，确保停止所有服务
cleanup() {
    echo ""
    info "正在停止所有服务..."
    
    # 停止 GitHub 知识库同步（包括 github_repo_watcher 和 webhook_server）
    stop_github_kb_sync
    
    # 停止 KB Service
    stop_kb_service
    
    success "所有服务已停止"
    exit 0
}

trap cleanup INT TERM EXIT

# 运行主函数
main "$@"
