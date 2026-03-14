#!/bin/bash
#
# GitHub Agent V2 启动脚本
#

# 错误处理：遇到错误继续执行，但会报告
set +e

# 颜色定义 (使用 ANSI 转义序列)
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
MAGENTA=$'\033[0;35m'
NC=$'\033[0m' # No Color
BOLD=$'\033[1m'

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

# 检查是否为 DEBUG 模式
is_debug() {
    [[ "$LOG_LEVEL" == "DEBUG" ]]
}

# 打印信息
info() {
    echo "${BLUE}[INFO]${NC} $1"
}

success() {
    echo "${GREEN}[✓]${NC} $1"
}

warning() {
    echo "${YELLOW}[!]${NC} $1"
}

error() {
    echo "${RED}[✗]${NC} $1"
}

# DEBUG 输出
debug() {
    if is_debug; then
        echo "${MAGENTA}[DEBUG]${NC} $1"
    fi
}

step() {
    echo ""
    echo "${CYAN}${BOLD}▶ $1${NC}"
    if is_debug; then
        echo "${MAGENTA}────────────────────────────────────────────────────────${NC}"
    fi
}

# 显示 Banner
show_banner() {
    echo ""
    echo "${MAGENTA}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo "${MAGENTA}${BOLD}║${NC}            ${CYAN}${BOLD}GitHub Agent V2${NC} - 智能 Issue 处理系统           ${MAGENTA}${BOLD}║${NC}"
    echo "${MAGENTA}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# 检查依赖
check_dependencies() {
    step "步骤 1/6: 检查环境依赖"
    
    if is_debug; then
        debug "项目目录: $PROJECT_DIR"
        debug "虚拟环境: $VENV_DIR"
        debug "PATH: $PATH"
    fi
    
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
        if is_debug; then
            debug "Python 路径: $(which python3)"
            debug "Pip 版本: $(pip --version)"
        fi
    fi
    
    # 激活虚拟环境
    source "$VENV_DIR/bin/activate"
    
    # 检查并安装依赖
    if [ ! -f "$VENV_DIR/.dependencies_installed" ] || [ "$PROJECT_DIR/requirements.txt" -nt "$VENV_DIR/.dependencies_installed" ]; then
        info "安装/更新依赖..."
        if is_debug; then
            pip install --upgrade pip 2>&1 | head -5
            pip install -r "$PROJECT_DIR/requirements.txt" 2>&1 | tail -10
        else
            pip install -q --upgrade pip
            pip install -q -r "$PROJECT_DIR/requirements.txt"
        fi
        touch "$VENV_DIR/.dependencies_installed"
        success "依赖安装完成"
    else
        success "依赖已安装"
        if is_debug; then
            debug "依赖检查跳过（已安装且未过期）"
        fi
    fi
    
    # 检查 Ollama
    OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        OLLAMA_MODELS=$(curl -s "$OLLAMA_HOST/api/tags" | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join([m['name'] for m in d.get('models',[])][:3]))" 2>/dev/null || echo "unknown")
        success "Ollama 服务正常 (${OLLAMA_MODELS})"
        if is_debug; then
            debug "Ollama 地址: $OLLAMA_HOST"
            debug "可用模型:"
            curl -s "$OLLAMA_HOST/api/tags" | python3 -c "import sys,json; [print(f'  - {m[\"name\"]}') for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null || true
        fi
    else
        warning "Ollama 服务未启动 (${OLLAMA_HOST})"
        if is_debug; then
            debug "检查命令: curl -s $OLLAMA_HOST/api/tags"
        fi
    fi
    
    echo ""
}

# 检查环境变量
check_env() {
    step "步骤 2/6: 检查配置"
    
    if is_debug; then
        debug "检查环境变量..."
        debug "GITHUB_APP_ID: ${GITHUB_APP_ID:-'(未设置)'}"
        debug "GITHUB_PRIVATE_KEY_PATH: ${GITHUB_PRIVATE_KEY_PATH:-'(未设置)'}"
        debug "GITHUB_WEBHOOK_SECRET: ${GITHUB_WEBHOOK_SECRET:0:3}***"
    fi
    
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
    
    echo ""
    echo "  ${BOLD}工作目录:${NC}"
    echo "    STATEDIR: ${GITHUB_AGENT_STATEDIR:-/tmp/github-agent-state}"
    
    if is_debug; then
        echo ""
        echo "  ${BOLD}DEBUG 配置:${NC}"
        echo "    LOG_LEVEL: ${LOG_LEVEL}"
        echo "    KB_SERVICE_URL: ${KB_SERVICE_URL}"
        echo "    OLLAMA_HOST: ${OLLAMA_HOST}"
    fi
    
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
    
    if is_debug; then
        debug "检查知识库服务: $kb_url"
        debug "健康检查: curl -s $kb_url/health"
    fi
    
    if curl -s "$kb_url/health" > /dev/null 2>&1; then
        local stats=$(curl -s "$kb_url/stats" 2>/dev/null)
        local doc_count=$(echo "$stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_documents',0))" 2>/dev/null || echo "0")
        local model=$(echo "$stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('embedding_model','unknown'))" 2>/dev/null || echo "unknown")
        
        success "知识库服务就绪"
        echo ""
        echo "  ${BOLD}服务信息:${NC}"
        echo "    服务地址: ${CYAN}${kb_url}${NC}"
        echo "    文档数量: ${BOLD}${doc_count}${NC}"
        echo "    嵌入模型: ${CYAN}${model}${NC}"
        echo "    向量存储: ${GREEN}ChromaDB${NC} (持久化 + HNSW)"
        
        if is_debug; then
            echo ""
            echo "  ${BOLD}DEBUG 详情:${NC}"
            echo "    KB_EMBEDDING_MODEL: ${KB_EMBEDDING_MODEL:-'(使用默认: nomic-embed-text)'}"
            echo "    KB_EMBEDDING_HOST: ${KB_EMBEDDING_HOST:-'(使用默认: http://localhost:11434)'}"
            echo "    ChromaDB: ${GITHUB_AGENT_STATEDIR:-/tmp/github-agent-state}/chroma_db"
        fi
        echo ""
    else
        warning "知识库服务未就绪"
        echo ""
        echo "  ${BOLD}诊断信息:${NC}"
        echo "    服务地址: ${CYAN}${kb_url}${NC}"
        echo ""
        echo "  ${BOLD}可能原因:${NC}"
        echo "    1. KB Service 未启动"
        echo "    2. 服务地址配置错误"
        echo "    3. 网络连接问题"
        echo ""
        echo "  ${BOLD}解决方案:${NC}"
        echo "    1. 检查 KB Service 是否运行:"
        echo "       ${CYAN}curl ${kb_url}/health${NC}"
        echo "    2. 手动启动 KB Service:"
        echo "       ${CYAN}python3 knowledge_base/kb_service.py${NC}"
        echo "    3. 检查环境变量 KB_SERVICE_URL 配置"
        echo ""
    fi
}

# 启动 KB Service
start_kb_service() {
    step "步骤 4/6: 启动知识库服务"
    
    # 服务监听配置（用于启动服务）
    KB_HOST="${KB_SERVICE_HOST:-0.0.0.0}"
    KB_PORT="${KB_SERVICE_PORT:-8000}"
    # 服务连接配置（用于检查连接）
    KB_URL="${KB_SERVICE_URL:-http://$KB_HOST:$KB_PORT}"
    
    if is_debug; then
        debug "KB_SERVICE_HOST: $KB_HOST"
        debug "KB_SERVICE_PORT: $KB_PORT"
        debug "KB_SERVICE_URL: $KB_URL"
        debug "检查命令: curl -s $KB_URL/health"
    fi
    
    # 检查嵌入模型配置
    EMBED_MODEL="${KB_EMBEDDING_MODEL:-nomic-embed-text}"
    
    # 检查是否已有 KB Service 在运行
    if curl -s "$KB_URL/health" > /dev/null 2>&1; then
        # 检查当前运行的服务是否使用了正确的模型
        local current_model=$(curl -s "$KB_URL/stats" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('embedding_model','unknown'))" 2>/dev/null || echo "unknown")
        
        if [ "$current_model" = "$EMBED_MODEL" ]; then
            success "知识库服务已在运行"
            echo ""
            echo "  ${BOLD}服务地址:${NC} ${CYAN}${KB_URL}${NC}"
            show_kb_status
            return 0
        else
            warning "知识库服务配置已变更: ${current_model} → ${EMBED_MODEL}"
            info "正在重启 KB Service..."
            # 停止现有服务
            pkill -f "kb_service.py" 2>/dev/null || true
            sleep 2
        fi
    fi
    OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
    
    info "使用嵌入模型: ${EMBED_MODEL}"
    
    if ! curl -s "$OLLAMA_HOST/api/tags" | grep -q "${EMBED_MODEL}"; then
        warning "${EMBED_MODEL} 模型未找到，正在拉取..."
        info "运行: ollama pull ${EMBED_MODEL}"
        ollama pull ${EMBED_MODEL} || {
            error "拉取 ${EMBED_MODEL} 模型失败"
            return 1
        }
        success "${EMBED_MODEL} 模型已就绪"
    fi
    
    # 后台启动 KB Service
    info "正在启动 KB Service $KB_HOST:$KB_PORT..."
    info "嵌入模型: ${EMBED_MODEL}"
    info "状态目录: ${GITHUB_AGENT_STATEDIR:-/tmp/github-agent-state}"
    cd "$PROJECT_DIR"
    
    # 使用 nohup + & 后台运行
    # 显式传递 GITHUB_AGENT_STATEDIR 环境变量
    nohup env GITHUB_AGENT_STATEDIR="${GITHUB_AGENT_STATEDIR:-/tmp/github-agent-state}" \
        python3 knowledge_base/kb_service.py \
        --host "$KB_HOST" \
        --port "$KB_PORT" \
        --embedding-model "${EMBED_MODEL}" > /tmp/kb_service.log 2>&1 &
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
    pkill -f "kb_service.py" 2>/dev/null || true
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
        info "GitHub 知识库同步未启用"
        if is_debug; then
            echo ""
            echo "  ${BOLD}当前配置:${NC}"
            echo "    KB_GITHUB_SYNC_ENABLED: ${KB_GITHUB_SYNC_ENABLED:-'(未设置)'}"
            echo ""
            echo "  ${BOLD}启用方式:${NC}"
            echo "    设置 ${CYAN}KB_GITHUB_SYNC_ENABLED=true${NC} 以启用"
            echo "    设置 ${CYAN}KB_REPO=owner/repo${NC} 指定仓库"
        fi
        echo ""
        return 0
    fi
    
    # 检查 GitHub Token
    check_github_token
    
    local repo="${KB_REPO:-tangjie133/knowledge-base}"
    local branch="${KB_BRANCH:-main}"
    
    echo ""
    echo "  ${BOLD}同步配置:${NC}"
    echo "    仓库: ${CYAN}${repo}${NC}"
    echo "    分支: ${CYAN}${branch}${NC}"
    [ -n "$http_proxy" ] && echo "    代理: ${CYAN}${http_proxy}${NC}"
    if is_debug; then
        echo "    GITHUB_TOKEN: $([ -n "$GITHUB_TOKEN" ] && echo '${GREEN}已设置${NC}' || echo '${RED}未设置${NC}')"
        echo "    同步命令: ${CYAN}python3 scripts/github_repo_watcher.py --sync${NC}"
    fi
    echo ""
    
    cd "$PROJECT_DIR"
    
    # 前台执行同步，等待完成
    info "开始同步..."
    echo ""
    
    # 根据日志级别调整 Python 日志
    if is_debug; then
        LOG_LEVEL=DEBUG python3 scripts/github_repo_watcher.py --sync
    else
        python3 scripts/github_repo_watcher.py --sync 2>&1 | grep -E '(🔄|📋|📊|✅|❌|✓)' || true
    fi
    
    local sync_status=$?
    
    if [ $sync_status -eq 0 ]; then
        success "同步完成"
        echo ""
    else
        warning "同步失败或部分失败"
        if is_debug; then
            echo ""
            echo "  ${BOLD}排查步骤:${NC}"
            echo "    1. 检查网络: ${CYAN}curl -I https://api.github.com${NC}"
            echo "    2. 检查代理: ${CYAN}echo \$HTTP_PROXY${NC}"
            echo "    3. 检查 Token: ${CYAN}python3 -c \"import os; print('OK' if os.getenv('GITHUB_TOKEN') else 'MISSING')\"${NC}"
            echo "    4. 手动调试: ${CYAN}LOG_LEVEL=DEBUG python3 scripts/github_repo_watcher.py --sync${NC}"
        else
            echo ""
            echo "  使用 ${CYAN}LOG_LEVEL=DEBUG ./scripts/start.sh${NC} 查看详细错误"
        fi
        echo ""
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
    local kb_repo="${KB_REPO:-tangjie133/knowledge-base}"
    
    step "步骤 5/6: 启动后台监控"
    
    if is_debug; then
        debug "KB_GITHUB_SYNC_ENABLED: ${KB_GITHUB_SYNC_ENABLED}"
        debug "KB_SYNC_INTERVAL: ${sync_interval}"
        debug "KB_WEBHOOK_ENABLED: ${webhook_enabled}"
        debug "KB_REPO: ${kb_repo}"
    fi
    
    local daemon_count=0
    
    # 如果启用了定时同步
    if [ "$sync_interval" -gt 0 ] 2>/dev/null; then
        nohup python3 scripts/github_repo_watcher.py --daemon --interval "$sync_interval" > /tmp/github_kb_sync.log 2>&1 &
        WATCHER_PID=$!
        echo $WATCHER_PID > "$WATCHER_PID_FILE"
        success "定时同步已启动"
        echo ""
        echo "  ${BOLD}监控配置:${NC}"
        echo "    监控仓库: ${CYAN}${kb_repo}${NC}"
        echo "    同步间隔: 每 ${BOLD}${sync_interval}${NC} 秒"
        echo "    日志文件: ${CYAN}/tmp/github_kb_sync.log${NC}"
        echo "    进程 PID: ${YELLOW}${WATCHER_PID}${NC}"
        echo ""
        daemon_count=$((daemon_count + 1))
    fi
    
    # 如果启用了 Webhook
    if [ "$webhook_enabled" == "true" ]; then
        nohup python3 scripts/github_webhook_server.py --port "$webhook_port" > /tmp/github_webhook.log 2>&1 &
        WEBHOOK_PID=$!
        echo $WEBHOOK_PID > "$WEBHOOK_PID_FILE"
        success "Webhook 服务器已启动"
        
        # 获取本机 IP
        local ip=$(hostname -I | awk '{print $1}')
        echo ""
        echo "  ${BOLD}Webhook 配置:${NC}"
        echo "    服务地址: ${CYAN}http://0.0.0.0:${webhook_port}${NC}"
        echo "    日志文件: ${CYAN}/tmp/github_webhook.log${NC}"
        echo "    进程 PID: ${YELLOW}${WEBHOOK_PID}${NC}"
        echo ""
        echo "  ${YELLOW}配置提示:${NC} 在 GitHub 仓库设置 Webhook"
        echo "    Payload URL: ${CYAN}http://${ip}:${webhook_port}/webhook${NC}"
        echo "    Content type: ${CYAN}application/json${NC}"
        echo "    Secret:       ${KB_WEBHOOK_SECRET:-'(未设置)'}"
        echo "    事件:         ${CYAN}Just the push event${NC}"
        echo ""
        daemon_count=$((daemon_count + 1))
    fi
    
    if [ "$daemon_count" -eq 0 ]; then
        info "后台监控未启用"
        echo ""
        echo "  ${BOLD}启用方式:${NC}"
        echo "    定时同步: 设置 ${CYAN}KB_SYNC_INTERVAL=300${NC}（秒）"
        echo "    Webhook:  设置 ${CYAN}KB_WEBHOOK_ENABLED=true${NC}"
        echo ""
    fi
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
    echo "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo "${GREEN}${BOLD}║${NC}                      🚀 服务启动就绪                          ${GREEN}${BOLD}║${NC}"
    echo "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # 核心服务状态
    echo "  ${BOLD}核心服务状态:${NC}"
    echo ""
    
    # Ollama
    if curl -s "$ollama_host/api/tags" > /dev/null 2>&1; then
        echo "    ${GREEN}✓${NC} ${BOLD}Ollama${NC}         ${GREEN}运行中${NC}  ${CYAN}${ollama_host}${NC}"
    else
        echo "    ${RED}✗${NC} ${BOLD}Ollama${NC}         ${RED}未连接${NC}  ${ollama_host}"
    fi
    
    # KB Service
    if curl -s "$kb_url/stats" > /dev/null 2>&1; then
        local doc_count=$(curl -s "$kb_url/stats" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_documents',0))" 2>/dev/null)
        echo "    ${GREEN}✓${NC} ${BOLD}知识库服务${NC}     ${GREEN}运行中${NC}  ${kb_url} (${doc_count} 文档)"
    else
        echo "    ${RED}✗${NC} ${BOLD}知识库服务${NC}     ${RED}未启动${NC}  ${kb_url}"
    fi
    
    # GitHub KB 同步
    if is_github_kb_enabled; then
        echo "    ${GREEN}✓${NC} ${BOLD}GitHub 同步${NC}    ${GREEN}已启用${NC}  ${KB_REPO:-tangjie133/knowledge-base}"
    else
        echo "    ${YELLOW}!${NC} ${BOLD}GitHub 同步${NC}    ${YELLOW}未启用${NC}"
    fi
    echo ""
    
    # 访问地址
    echo "  ${BOLD}访问地址:${NC}"
    echo ""
    printf "    %-15s ${CYAN}http://${HOST}:${PORT}${NC}\n" "主服务:"
    printf "    %-15s ${CYAN}http://${HOST}:${PORT}/health${NC}\n" "健康检查:"
    printf "    %-15s ${CYAN}http://${HOST}:${PORT}/webhook/github${NC}\n" "Webhook:"
    printf "    %-15s ${CYAN}${KB_SERVICE_URL:-http://localhost:8000}${NC}\n" "知识库 API:"
    echo ""
    
    # 日志文件位置
    echo "  ${BOLD}日志文件:${NC}"
    echo ""
    printf "    %-15s ${CYAN}/tmp/kb_service.log${NC}\n" "知识库服务:"
    if [ -f "$WATCHER_PID_FILE" ]; then
        printf "    %-15s ${CYAN}/tmp/github_kb_sync.log${NC}\n" "定时同步:"
    fi
    if [ -f "$WEBHOOK_PID_FILE" ]; then
        printf "    %-15s ${CYAN}/tmp/github_webhook.log${NC}\n" "Webhook:"
    fi
    echo ""
    
    # 使用提示
    echo "  ${BOLD}使用提示:${NC}"
    echo ""
    echo "    1. 在 GitHub Issue 中提及 @agent 来触发智能处理"
    echo "    2. 按 Ctrl+C 停止所有服务"
    echo "    3. 使用 tail -f /tmp/kb_service.log 查看实时日志"
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
