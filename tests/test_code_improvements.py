#!/usr/bin/env python3
"""
代码优化验证测试

测试内容：
1. CodeAnalyzer - 代码分析器
2. SafeCodeModifier - 模糊匹配
3. ChangeValidator - 修改验证
4. 集成测试 - 完整流程
"""

import sys
import tempfile
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from code_executor.code_analyzer import CodeAnalyzer, analyze_repository
from code_executor.safe_modifier import SafeCodeModifier
from code_executor.change_validator import ChangeValidator


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")


def print_result(name, passed, details=""):
    status = f"{Colors.GREEN}✅ PASS{Colors.END}" if passed else f"{Colors.RED}❌ FAIL{Colors.END}"
    print(f"{status} - {name}")
    if details:
        print(f"   {details}")


# =============================================================================
# 测试 1: CodeAnalyzer
# =============================================================================

def test_code_analyzer():
    """测试代码分析器"""
    print_header("测试 1: CodeAnalyzer 代码分析器")
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试仓库
        repo = Path(tmpdir)
        
        # 创建 Python 文件
        (repo / "sensor.py").write_text("""
import time
import random

def read_temperature():
    return random.randint(20, 30)

def main():
    while True:
        temp = read_temperature()
        print(f"Temperature: {temp}C")
        time.sleep(1)

if __name__ == "__main__":
    main()
""")
        
        # 创建 Arduino 文件
        (repo / "sensor.ino").write_text("""
#include <Wire.h>
#include <Adafruit_Sensor.h>

#define SENSOR_PIN A0
#define LED_PIN 13

void setup() {
    Serial.begin(9600);
    pinMode(SENSOR_PIN, INPUT);
    pinMode(LED_PIN, OUTPUT);
    Wire.begin();
}

void loop() {
    int value = analogRead(SENSOR_PIN);
    float voltage = value * 5.0 / 1023.0;
    
    Serial.print("Voltage: ");
    Serial.println(voltage);
    
    if (voltage > 2.5) {
        digitalWrite(LED_PIN, HIGH);
    } else {
        digitalWrite(LED_PIN, LOW);
    }
    
    delay(1000);
}

void handleInterrupt() {
    // ISR
}
""")
        
        analyzer = CodeAnalyzer()
        
        # 测试 1.1: 提取关键词
        print("\n1.1 关键词提取测试")
        keywords = analyzer._extract_keywords(
            "Fix analogRead on pin A0",
            "The sensor connected to analog pin A0 is not working correctly. Using Wire library."
        )
        
        if "A0" in keywords["arduino_pins"]:
            print_result("提取 Arduino 引脚", True)
            passed += 1
        else:
            print_result("提取 Arduino 引脚", False, f"期望 A0, 得到 {keywords['arduino_pins']}")
            failed += 1
        
        if "Wire" in keywords["libraries"]:
            print_result("提取库依赖", True)
            passed += 1
        else:
            print_result("提取库依赖", False, f"期望 Wire, 得到 {keywords['libraries']}")
            failed += 1
        
        # 测试 1.2: Python 文件分析
        print("\n1.2 Python 文件分析")
        py_analysis = analyzer._analyze_python_file("sensor.py", (repo / "sensor.py").read_text())
        
        if "read_temperature" in py_analysis.functions:
            print_result("提取 Python 函数", True)
            passed += 1
        else:
            print_result("提取 Python 函数", False)
            failed += 1
        
        if "random" in py_analysis.includes:
            print_result("提取 Python import", True)
            passed += 1
        else:
            print_result("提取 Python import", False)
            failed += 1
        
        # 测试 1.3: Arduino 文件分析
        print("\n1.3 Arduino 文件分析")
        ino_analysis = analyzer._analyze_arduino_cpp_file("sensor.ino", (repo / "sensor.ino").read_text())
        
        if ino_analysis.language == "arduino":
            print_result("识别 Arduino 语言", True)
            passed += 1
        else:
            print_result("识别 Arduino 语言", False, f"得到 {ino_analysis.language}")
            failed += 1
        
        if 14 in ino_analysis.pins:  # A0 = 14
            print_result("提取引脚 A0", True)
            passed += 1
        else:
            print_result("提取引脚 A0", False, f"得到 {ino_analysis.pins}")
            failed += 1
        
        if "Wire" in ino_analysis.libraries:
            print_result("提取 Arduino 库", True)
            passed += 1
        else:
            print_result("提取 Arduino 库", False)
            failed += 1
        
        # 测试 1.4: 完整 Issue 分析
        print("\n1.4 完整 Issue 分析")
        files, graph, reasoning = analyzer.analyze_for_issue(
            repo,
            "Fix analogRead not working",
            "The sensor on pin A0 always returns 0, check Wire library configuration"
        )
        
        if "sensor.ino" in files:
            print_result("匹配到正确的 Arduino 文件", True)
            passed += 1
        else:
            print_result("匹配到正确的 Arduino 文件", False, f"得到 {files}")
            failed += 1
        
        if "sensor.py" not in files:
            print_result("未匹配无关的 Python 文件", True)
            passed += 1
        else:
            print_result("未匹配无关的 Python 文件", False, "错误地包含了 sensor.py")
            failed += 1
    
    return passed, failed


# =============================================================================
# 测试 2: 模糊匹配
# =============================================================================

def test_fuzzy_matching():
    """测试模糊匹配功能"""
    print_header("测试 2: SafeCodeModifier 模糊匹配")
    
    passed = 0
    failed = 0
    
    modifier = SafeCodeModifier(code_generator=None)
    
    test_content = """#include <Wire.h>

void setup() {
    Serial.begin(9600);
    pinMode(A0, INPUT);
}

void loop() {
    int value = analogRead(A0);
    Serial.println(value);
    delay(1000);
}
"""
    
    # 测试 2.1: 精确匹配
    print("\n2.1 精确匹配")
    try:
        result, method = modifier._fuzzy_search_replace(
            test_content,
            "    pinMode(A0, INPUT);",
            "    pinMode(A0, INPUT_PULLUP);"
        )
        if method == "exact" and "INPUT_PULLUP" in result:
            print_result("精确匹配成功", True)
            passed += 1
        else:
            print_result("精确匹配成功", False, f"方法: {method}")
            failed += 1
    except Exception as e:
        print_result("精确匹配成功", False, str(e))
        failed += 1
    
    # 测试 2.2: 行尾空白差异
    print("\n2.2 行尾空白差异")
    try:
        result, method = modifier._fuzzy_search_replace(
            test_content,
            "    Serial.begin(9600);   ",  # 额外空格
            "    Serial.begin(115200);"
        )
        if "normalized" in method and "115200" in result:
            print_result("规范化匹配成功", True)
            passed += 1
        else:
            print_result("规范化匹配成功", False, f"方法: {method}")
            failed += 1
    except Exception as e:
        print_result("规范化匹配成功", False, str(e))
        failed += 1
    
    # 测试 2.3: 多行匹配
    print("\n2.3 多行匹配")
    try:
        result, method = modifier._fuzzy_search_replace(
            test_content,
            """void loop() {
    int value = analogRead(A0);""",
            """void loop() {
    // 平滑滤波
    int value = analogRead(A0);"""
        )
        if "平滑滤波" in result:
            print_result("多行匹配成功", True)
            passed += 1
        else:
            print_result("多行匹配成功", False)
            failed += 1
    except Exception as e:
        print_result("多行匹配成功", False, str(e))
        failed += 1
    
    # 测试 2.4: 完全不匹配（应该失败）
    print("\n2.4 完全不匹配（应该失败）")
    try:
        result, method = modifier._fuzzy_search_replace(
            test_content,
            "这行代码不存在",
            "替换内容"
        )
        print_result("正确拒绝无效匹配", False, "应该抛出异常")
        failed += 1
    except ValueError:
        print_result("正确拒绝无效匹配", True)
        passed += 1
    
    return passed, failed


# =============================================================================
# 测试 3: 修改验证
# =============================================================================

def test_change_validation():
    """测试修改验证功能"""
    print_header("测试 3: ChangeValidator 修改验证")
    
    passed = 0
    failed = 0
    
    validator = ChangeValidator()
    
    # 测试 3.1: 有效的 Arduino 代码
    print("\n3.1 有效的 Arduino 代码验证")
    valid_ino = """
#include <Wire.h>

void setup() {
    Serial.begin(9600);
    pinMode(A0, INPUT);
}

void loop() {
    int value = analogRead(A0);
    Serial.println(value);
    delay(1000);
}
"""
    result = validator.validate_arduino_cpp_file("test.ino", valid_ino)
    if result.is_valid:
        print_result("有效代码验证通过", True)
        passed += 1
    else:
        print_result("有效代码验证通过", False, result.errors)
        failed += 1
    
    # 测试 3.2: 括号不匹配
    print("\n3.2 括号不匹配检测")
    bad_brackets = """
void setup() {
    Serial.begin(9600);
    pinMode(A0, INPUT;
}
"""
    result = validator.validate_arduino_cpp_file("bad.ino", bad_brackets)
    if not result.is_valid and "括号" in str(result.errors):
        print_result("括号不匹配检测", True)
        passed += 1
    else:
        print_result("括号不匹配检测", False, f"错误: {result.errors}")
        failed += 1
    
    # 测试 3.3: 缺少 setup/loop 警告
    print("\n3.3 Arduino 结构警告")
    incomplete = """
#include <Wire.h>
void initSensor() {
    Wire.begin();
}
"""
    result = validator.validate_arduino_cpp_file("incomplete.ino", incomplete)
    if "setup()" in str(result.warnings) and "loop()" in str(result.warnings):
        print_result("缺少函数警告", True)
        passed += 1
    else:
        print_result("缺少函数警告", False, f"警告: {result.warnings}")
        failed += 1
    
    # 测试 3.4: 修改完整性验证
    print("\n3.4 修改完整性验证")
    original = """
def helper():
    return 1

def main():
    helper()
"""
    modified = """
def helper():
    return 1

def main():
    # 添加日志
    print("Starting")
    helper()
"""
    result = validator.validate_modification("test.py", original, modified)
    if result.is_valid:
        print_result("有效修改验证通过", True)
        passed += 1
    else:
        print_result("有效修改验证通过", False, result.errors)
        failed += 1
    
    # 测试 3.5: 无变化检测
    print("\n3.5 无变化检测")
    result = validator.validate_modification("test.py", original, original)
    if not result.is_valid and "未变化" in str(result.errors):
        print_result("无变化检测", True)
        passed += 1
    else:
        print_result("无变化检测", False, f"错误: {result.errors}")
        failed += 1
    
    # 测试 3.6: Python 语法错误
    print("\n3.6 Python 语法错误检测")
    bad_python = """
def broken(
    print("missing parenthesis")
"""
    result = validator.validate_python_file("bad.py", bad_python)
    if not result.is_valid:
        print_result("Python 语法错误检测", True)
        passed += 1
    else:
        print_result("Python 语法错误检测", False)
        failed += 1
    
    return passed, failed


# =============================================================================
# 测试 4: 集成测试
# =============================================================================

def test_integration():
    """测试完整集成流程"""
    print_header("测试 4: 集成测试")
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        
        # 创建测试仓库
        (repo / "project.ino").write_text("""
#include <Wire.h>

void setup() {
    Serial.begin(9600);
}

void loop() {
    int value = analogRead(A0);
    Serial.println(value);
}
""")
        
        # 4.1: 分析 → 匹配
        print("\n4.1 分析到匹配流程")
        analyzer = CodeAnalyzer()
        files, graph, reasoning = analyzer.analyze_for_issue(
            repo,
            "Fix analogRead for temperature sensor",
            "The temperature sensor on A0 needs better filtering"
        )
        
        if "project.ino" in files:
            print_result("分析匹配流程", True)
            passed += 1
        else:
            print_result("分析匹配流程", False, f"得到 {files}")
            failed += 1
        
        # 4.2: 验证器集成
        print("\n4.2 验证器集成")
        validator = ChangeValidator()
        content = (repo / "project.ino").read_text()
        
        # 模拟修改
        modified = content.replace("9600", "115200")
        result = validator.validate_modification("project.ino", content, modified)
        
        if result.is_valid and "115200" in modified:
            print_result("验证器集成", True)
            passed += 1
        else:
            print_result("验证器集成", False, result.errors)
            failed += 1
    
    return passed, failed


# =============================================================================
# 主函数
# =============================================================================

def main():
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}代码优化验证测试{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    total_passed = 0
    total_failed = 0
    
    try:
        p, f = test_code_analyzer()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"{Colors.RED}CodeAnalyzer 测试异常: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        total_failed += 5
    
    try:
        p, f = test_fuzzy_matching()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"{Colors.RED}模糊匹配测试异常: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        total_failed += 4
    
    try:
        p, f = test_change_validation()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"{Colors.RED}验证测试异常: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        total_failed += 6
    
    try:
        p, f = test_integration()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"{Colors.RED}集成测试异常: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        total_failed += 2
    
    # 总结
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}测试结果汇总{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    total = total_passed + total_failed
    print(f"总计: {total} 项测试")
    print(f"{Colors.GREEN}通过: {total_passed}{Colors.END}")
    print(f"{Colors.RED}失败: {total_failed}{Colors.END}")
    print(f"通过率: {total_passed/total*100:.1f}%")
    
    if total_failed == 0:
        print(f"\n{Colors.GREEN}🎉 所有测试通过！优化实施成功！{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.YELLOW}⚠️ 有 {total_failed} 项测试失败，请检查{Colors.END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
