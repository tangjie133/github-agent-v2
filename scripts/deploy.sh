#!/bin/bash
#
# GitHub Agent V2 部署脚本
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 项目目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

# 部署配置
DEPLOY_DIR="${DEPLOY_DIR:-/opt/github-agent-v2}"
SERVICE_NAME="${SERVICE_NAME:-github-agent-v2}"
USER="${DEPLOY_USER:-github-agent}"

# 安装系统依赖
install_system_deps() {
    info "安装系统依赖..."
    
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip git
    elif command -v yum &> /dev/null; then
        # RHEL/CentOS
        sudo yum install -y python3 python3-pip git
    else
        warning "未知的包管理器，请手动安装 Python3 和 Git"
    fi
    
    success "系统依赖安装完成"
}

# 创建用户
create_user() {
    info "创建运行用户..."
    
    if ! id "$USER" &>/dev/null; then
        sudo useradd -r -s /bin/false -d "$DEPLOY_DIR" "$USER"
        success "用户 $USER 创建完成"
    else
        info "用户 $USER 已存在"
    fi
}

# 复制项目文件
deploy_files() {
    info "部署项目文件..."
    
    # 创建部署目录
    sudo mkdir -p "$DEPLOY_DIR"
    
    # 复制文件
    sudo cp -r "$PROJECT_DIR"/* "$DEPLOY_DIR/"
    sudo cp -r "$PROJECT_DIR"/.* "$DEPLOY_DIR/" 2>/dev/null || true
    
    # 设置权限
    sudo chown -R "$USER:$USER" "$DEPLOY_DIR"
    
    success "文件部署完成"
}

# 安装 Python 依赖
install_python_deps() {
    info "安装 Python 依赖..."
    
    cd "$DEPLOY_DIR"
    
    # 创建虚拟环境
    sudo -u "$USER" python3 -m venv "$VENV_DIR"
    
    # 安装依赖
    sudo -u "$USER" "$VENV_DIR/bin/pip" install --upgrade pip
    sudo -u "$USER" "$VENV_DIR/bin/pip" install -r requirements.txt
    
    success "Python 依赖安装完成"
}

# 创建 systemd 服务
create_service() {
    info "创建 systemd 服务..."
    
    cat << EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=GitHub Agent V2
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DEPLOY_DIR
Environment=PATH=$VENV_DIR/bin
EnvironmentFile=$DEPLOY_DIR/.env
ExecStart=$VENV_DIR/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    success "服务创建完成"
}

# 配置日志轮转
setup_logrotate() {
    info "配置日志轮转..."
    
    cat << EOF | sudo tee /etc/logrotate.d/$SERVICE_NAME
/var/log/$SERVICE_NAME/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $USER $USER
}
EOF
    
    # 创建日志目录
    sudo mkdir -p "/var/log/$SERVICE_NAME"
    sudo chown "$USER:$USER" "/var/log/$SERVICE_NAME"
    
    success "日志轮转配置完成"
}

# 验证部署
verify_deployment() {
    info "验证部署..."
    
    # 检查服务文件
    if [ ! -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
        error "服务文件未创建"
        return 1
    fi
    
    # 检查 Python 依赖
    if [ ! -f "$VENV_DIR/bin/python" ]; then
        error "Python 虚拟环境未创建"
        return 1
    fi
    
    success "部署验证通过"
}

# 显示使用说明
show_usage() {
    echo ""
    echo "=================================="
    echo "  部署完成！"
    echo "=================================="
    echo ""
    echo "使用方法:"
    echo "  启动服务: sudo systemctl start $SERVICE_NAME"
    echo "  停止服务: sudo systemctl stop $SERVICE_NAME"
    echo "  查看状态: sudo systemctl status $SERVICE_NAME"
    echo "  查看日志: sudo journalctl -u $SERVICE_NAME -f"
    echo ""
    echo "文件位置:"
    echo "  项目目录: $DEPLOY_DIR"
    echo "  日志目录: /var/log/$SERVICE_NAME"
    echo "  服务配置: /etc/systemd/system/$SERVICE_NAME.service"
    echo ""
    echo "下一步:"
    echo "  1. 创建 $DEPLOY_DIR/.env 文件配置环境变量"
    echo "  2. 运行: sudo systemctl start $SERVICE_NAME"
    echo "  3. 检查状态: sudo systemctl status $SERVICE_NAME"
    echo ""
}

# 主函数
main() {
    echo "=================================="
    echo "  GitHub Agent V2 部署脚本"
    echo "=================================="
    echo ""
    
    # 检查 root 权限
    if [ "$EUID" -ne 0 ]; then
        error "请使用 sudo 运行此脚本"
        exit 1
    fi
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --user)
                USER="$2"
                shift 2
                ;;
            --dir)
                DEPLOY_DIR="$2"
                shift 2
                ;;
            --service-name)
                SERVICE_NAME="$2"
                shift 2
                ;;
            --skip-system-deps)
                SKIP_SYSTEM_DEPS=1
                shift
                ;;
            --help)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  --user <user>          运行用户 (默认: github-agent)"
                echo "  --dir <dir>            部署目录 (默认: /opt/github-agent-v2)"
                echo "  --service-name <name>  服务名称 (默认: github-agent-v2)"
                echo "  --skip-system-deps     跳过系统依赖安装"
                echo "  --help                 显示帮助"
                exit 0
                ;;
            *)
                error "未知选项: $1"
                exit 1
                ;;
        esac
    done
    
    info "部署配置:"
    echo "  用户: $USER"
    echo "  目录: $DEPLOY_DIR"
    echo "  服务: $SERVICE_NAME"
    echo ""
    
    read -p "确认部署? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "部署已取消"
        exit 0
    fi
    
    # 执行部署步骤
    [ -z "$SKIP_SYSTEM_DEPS" ] && install_system_deps
    create_user
    deploy_files
    install_python_deps
    create_service
    setup_logrotate
    verify_deployment
    
    show_usage
}

main "$@"
