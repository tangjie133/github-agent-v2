#!/bin/bash
#
# GitHub 仓库知识库同步配置脚本
#
# 用法: ./setup_github_kb.sh

set -e

echo "=============================================="
echo "  GitHub 仓库知识库同步配置"
echo "=============================================="
echo ""

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

# 获取用户输入
read -p "GitHub 仓库 (格式: owner/repo) [tangjie133/knowledge-base]: " REPO
REPO=${REPO:-"tangjie133/knowledge-base"}

read -p "分支名称 [main]: " BRANCH
BRANCH=${BRANCH:-"main"}

read -p "GitHub Token (用于私有仓库，可选): " TOKEN

read -p "Webhook Secret (用于签名验证，可选): " WEBHOOK_SECRET

# 写入 .env 文件
ENV_FILE="$(dirname "$0")/../.env"

info "写入配置到 .env 文件..."

# 检查是否已存在配置
if grep -q "KB_REPO" "$ENV_FILE" 2>/dev/null; then
    # 更新现有配置
    sed -i "s|KB_REPO=.*|KB_REPO=$REPO|" "$ENV_FILE"
    sed -i "s|KB_BRANCH=.*|KB_BRANCH=$BRANCH|" "$ENV_FILE"
    if [ -n "$TOKEN" ]; then
        sed -i "s|GITHUB_TOKEN=.*|GITHUB_TOKEN=$TOKEN|" "$ENV_FILE"
    fi
    if [ -n "$WEBHOOK_SECRET" ]; then
        sed -i "s|GITHUB_WEBHOOK_SECRET=.*|GITHUB_WEBHOOK_SECRET=$WEBHOOK_SECRET|" "$ENV_FILE"
    fi
else
    # 添加新配置
    cat >> "$ENV_FILE" << EOF

# GitHub 知识库同步配置
KB_REPO=$REPO
KB_BRANCH=$BRANCH
EOF
    if [ -n "$TOKEN" ]; then
        echo "GITHUB_TOKEN=$TOKEN" >> "$ENV_FILE"
    fi
    if [ -n "$WEBHOOK_SECRET" ]; then
        echo "GITHUB_WEBHOOK_SECRET=$WEBHOOK_SECRET" >> "$ENV_FILE"
    fi
fi

success "配置已保存到 .env 文件"
echo ""

# 检查依赖
info "检查依赖..."

if ! command -v pdftotext &> /dev/null; then
    warning "pdftotext 未安装，PDF 转换功能受限"
    echo "   安装命令: sudo apt-get install poppler-utils"
fi

if ! python3 -c "import requests" 2>/dev/null; then
    warning "requests 库未安装"
    echo "   安装命令: pip install requests"
fi

echo ""
echo "=============================================="
success "配置完成！"
echo "=============================================="
echo ""
echo "使用方式："
echo ""
echo "1. 手动同步一次："
echo "   python scripts/github_repo_watcher.py --sync"
echo ""
echo "2. 后台定时同步（每5分钟）："
echo "   python scripts/github_repo_watcher.py --daemon"
echo ""
echo "3. 启动 Webhook 服务器（实时同步）："
echo "   python scripts/github_webhook_server.py --port 9000"
echo ""
echo "   然后在 GitHub 仓库设置 Webhook："
echo "   - URL: http://$(hostname -I | awk '{print $1}'):9000/webhook"
echo "   - Secret: ${WEBHOOK_SECRET:-'不设置'}"
echo "   - 事件: Just the push event"
echo ""
