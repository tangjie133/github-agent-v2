#!/bin/bash
#
# 前台启动所有服务 - 适合调试
#

cd "$(dirname "$0")"
source venv/bin/activate

# 设置颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}  GitHub Agent V2 - 调试启动${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# 清理旧进程
echo "清理旧进程..."
pkill -f "kb_service\|main.py" 2>/dev/null
sleep 1

# 启动 KB Service（后台，日志到文件）
echo -e "${GREEN}[1/2]${NC} 启动 KB Service..."
python3 -m knowledge_base.kb_service > kb_service.log 2>&1 &
KB_PID=$!
echo "PID: $KB_PID"

# 等待就绪
echo -n "等待 KB Service 就绪"
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# 显示 KB 状态
echo ""
curl -s http://localhost:8000/stats | python3 -m json.tool
echo ""

# 启动主服务（前台，日志直接输出）
echo -e "${GREEN}[2/2]${NC} 启动主服务（前台模式）..."
echo -e "${BLUE}==================================${NC}"
echo ""

# 设置调试环境变量
export LOG_LEVEL=DEBUG
export PYTHONUNBUFFERED=1

# 启动主服务
trap 'echo ""; echo "停止 KB Service..."; kill $KB_PID 2>/dev/null; exit 0' INT
python3 main.py --port 8080
