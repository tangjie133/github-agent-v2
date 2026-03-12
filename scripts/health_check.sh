#!/bin/bash
#
# 服务健康检查脚本
#

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=================================="
echo "  服务健康检查"
echo "=================================="
echo ""

# 检查 KB Service
echo -n "KB Service (localhost:8000): "
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ 正常${NC}"
    DOC_COUNT=$(curl -s http://localhost:8000/stats | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_documents',0))" 2>/dev/null)
    echo "  文档数: $DOC_COUNT"
else
    echo -e "${RED}❌ 未运行${NC}"
fi
echo ""

# 检查 Ollama
echo -n "Ollama (localhost:11434): "
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 正常${NC}"
    MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join([m['name'] for m in d.get('models',[])[:2]]))" 2>/dev/null)
    echo "  模型: $MODELS"
else
    echo -e "${RED}❌ 未运行${NC}"
fi
echo ""

# 检查主服务
echo -n "主服务 (localhost:8080): "
if curl -s http://localhost:8080/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ 正常${NC}"
else
    echo -e "${RED}❌ 未运行${NC}"
fi
echo ""

# 检查进程
echo "进程状态:"
echo "  KB Service: $(pgrep -c -f 'kb_service') 个进程"
echo "  主服务: $(pgrep -c -f 'main.py') 个进程"
echo ""

# 检查端口
echo "端口监听:"
ss -tlnp 2>/dev/null | grep -E "8000|8080|11434" || netstat -tlnp 2>/dev/null | grep -E "8000|8080|11434" || echo "  未找到端口信息"
