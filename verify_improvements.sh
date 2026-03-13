#!/bin/bash
# 代码优化验证脚本
# 运行所有测试验证优化效果

echo "========================================"
echo "GitHub Agent V2 - 代码优化验证"
echo "========================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

echo "Step 1: 运行单元测试..."
echo "----------------------------------------"
python3 tests/test_code_improvements.py
UNIT_TEST_RESULT=$?
echo ""

echo "Step 2: 运行端到端场景测试..."
echo "----------------------------------------"
python3 tests/test_e2e_scenario.py
E2E_TEST_RESULT=$?
echo ""

echo "========================================"
echo "验证总结"
echo "========================================"

if [ $UNIT_TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ 单元测试通过${NC}"
else
    echo -e "${RED}❌ 单元测试失败${NC}"
fi

if [ $E2E_TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ 端到端测试通过${NC}"
else
    echo -e "${RED}❌ 端到端测试失败${NC}"
fi

if [ $UNIT_TEST_RESULT -eq 0 ] && [ $E2E_TEST_RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 所有验证通过！优化实施成功！${NC}"
    echo ""
    echo "优化内容:"
    echo "  1. CodeAnalyzer - 代码依赖分析"
    echo "  2. SafeCodeModifier - 模糊匹配 SEARCH/REPLACE"
    echo "  3. ChangeValidator - 修改后验证"
    echo ""
    exit 0
else
    echo ""
    echo -e "${YELLOW}⚠️ 部分测试失败，请检查${NC}"
    echo ""
    exit 1
fi
