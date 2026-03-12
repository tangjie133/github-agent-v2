#!/bin/bash
#
# GitHub Agent V2 调试启动脚本 - 前台运行，输出日志到终端
#

cd "$(dirname "$0")/.."
source venv/bin/activate

echo "=================================="
echo "  GitHub Agent V2 - 调试模式"
echo "=================================="
echo ""

# 设置日志级别为 DEBUG
export LOG_LEVEL=DEBUG
export PYTHONUNBUFFERED=1

# 先启动 KB Service（后台，但日志可见）
echo "[1/2] 启动 KB Service..."
python3 -m knowledge_base.kb_service --host 0.0.0.0 --port 8000 &
KB_PID=$!
echo "KB Service PID: $KB_PID"

# 等待 KB Service 就绪
echo "等待 KB Service 就绪..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ KB Service 就绪"
        break
    fi
    sleep 1
done

echo ""
echo "[2/2] 启动主服务..."
echo "=================================="
echo ""

# 启动主服务（前台，日志直接输出）
python3 main.py --port 8080

# 清理
echo ""
echo "正在停止 KB Service..."
kill $KB_PID 2>/dev/null
