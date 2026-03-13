#!/usr/bin/env python3
"""
端到端场景测试

模拟真实的 GitHub Issue 修复流程
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from code_executor.code_analyzer import CodeAnalyzer
from code_executor.change_validator import ChangeValidator


def test_scenario_1_sensor_filtering():
    """场景1: 添加传感器数据滤波"""
    print("\n" + "="*60)
    print("场景1: 传感器数据滤波优化")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        
        # 创建原始代码
        original_code = """#include <Wire.h>

#define SENSOR_PIN A0

void setup() {
    Serial.begin(9600);
    pinMode(SENSOR_PIN, INPUT);
}

void loop() {
    int rawValue = analogRead(SENSOR_PIN);
    Serial.println(rawValue);
    delay(100);
}
"""
        (repo / "sensor.ino").write_text(original_code)
        
        # 模拟 Issue
        issue_title = "Add smoothing filter to sensor readings"
        issue_body = """
The sensor readings from A0 are very noisy. 
Please add a moving average filter to smooth the data.
Current code reads raw value directly without any filtering.
"""
        
        print(f"Issue: {issue_title}")
        print(f"原始代码:\n{original_code}")
        
        # 1. 分析代码
        analyzer = CodeAnalyzer()
        files, graph, reasoning = analyzer.analyze_for_issue(
            repo, issue_title, issue_body
        )
        
        print(f"\n分析结果:")
        print(f"  建议修改文件: {files}")
        print(f"  检测到的引脚: {list(graph.files['sensor.ino'].pins.keys())}")
        
        # 验证分析结果
        assert 'sensor.ino' in files, "应该匹配到 sensor.ino"
        assert 14 in graph.files['sensor.ino'].pins, "应该检测到 A0 引脚"
        
        # 2. 模拟修改（实际场景中 AI 会生成）
        modified_code = """#include <Wire.h>

#define SENSOR_PIN A0
#define FILTER_SIZE 10

int readings[FILTER_SIZE];
int readIndex = 0;
int total = 0;
int average = 0;

void setup() {
    Serial.begin(9600);
    pinMode(SENSOR_PIN, INPUT);
    
    // Initialize filter array
    for (int i = 0; i < FILTER_SIZE; i++) {
        readings[i] = 0;
    }
}

void loop() {
    // Subtract the oldest reading
    total = total - readings[readIndex];
    
    // Read new value
    readings[readIndex] = analogRead(SENSOR_PIN);
    
    // Add the new reading to total
    total = total + readings[readIndex];
    
    // Advance to next position
    readIndex = readIndex + 1;
    
    // Wrap around if at end
    if (readIndex >= FILTER_SIZE) {
        readIndex = 0;
    }
    
    // Calculate average
    average = total / FILTER_SIZE;
    
    Serial.println(average);
    delay(100);
}
"""
        
        print(f"\n修改后代码:\n{modified_code}")
        
        # 3. 验证修改
        validator = ChangeValidator()
        result = validator.validate_modification(
            "sensor.ino", original_code, modified_code, issue_body
        )
        
        print(f"\n验证结果:")
        print(f"  有效: {result.is_valid}")
        print(f"  错误: {result.errors}")
        print(f"  警告: {result.warnings}")
        
        assert result.is_valid, f"修改应该有效: {result.errors}"
        
        # 4. 验证修改内容
        assert "FILTER_SIZE" in modified_code, "应该添加滤波器大小定义"
        assert "readings[" in modified_code, "应该使用数组存储历史值"
        assert "average" in modified_code, "应该计算平均值"
        
        print("\n✅ 场景1测试通过！")
        return True


def test_scenario_2_error_handling():
    """场景2: 添加错误处理"""
    print("\n" + "="*60)
    print("场景2: 添加传感器错误处理")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        
        original_code = """def read_temperature():
    return sensor.read()

def main():
    temp = read_temperature()
    print(f"Temperature: {temp}")
"""
        (repo / "main.py").write_text(original_code)
        
        issue_title = "Add error handling to read_temperature() function"
        issue_body = """
The read_temperature() function in main.py doesn't handle sensor errors.
Need to add try-except to catch IOError and return None on failure.
Please update the main.py file to include proper error handling.
"""
        
        print(f"Issue: {issue_title}")
        print(f"原始代码:\n{original_code}")
        
        # 分析
        analyzer = CodeAnalyzer()
        files, graph, reasoning = analyzer.analyze_for_issue(
            repo, issue_title, issue_body
        )
        
        print(f"\n分析结果:")
        print(f"  建议修改文件: {files}")
        print(f"  检测到的函数: {list(graph.files['main.py'].functions.keys())}")
        
        assert 'main.py' in files
        assert 'read_temperature' in graph.files['main.py'].functions
        
        # 模拟修改
        modified_code = """def read_temperature():
    try:
        return sensor.read()
    except IOError:
        print("Error: Failed to read temperature sensor")
        return None

def main():
    temp = read_temperature()
    if temp is not None:
        print(f"Temperature: {temp}")
    else:
        print("Warning: Using default temperature")
"""
        
        print(f"\n修改后代码:\n{modified_code}")
        
        # 验证
        validator = ChangeValidator()
        result = validator.validate_modification(
            "main.py", original_code, modified_code, issue_body
        )
        
        print(f"\n验证结果:")
        print(f"  有效: {result.is_valid}")
        print(f"  错误: {result.errors}")
        
        assert result.is_valid
        assert "try" in modified_code
        assert "except IOError" in modified_code
        
        print("\n✅ 场景2测试通过！")
        return True


def test_scenario_3_pin_config_fix():
    """场景3: 修复引脚配置"""
    print("\n" + "="*60)
    print("场景3: 修复 Arduino 引脚配置")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        
        original_code = """#include <Wire.h>

#define BUTTON_PIN 2
#define LED_PIN 13

void setup() {
    Serial.begin(9600);
    // Button pin not configured
    pinMode(LED_PIN, OUTPUT);
}

void loop() {
    int buttonState = digitalRead(BUTTON_PIN);
    if (buttonState == HIGH) {
        digitalWrite(LED_PIN, HIGH);
    } else {
        digitalWrite(LED_PIN, LOW);
    }
}
"""
        (repo / "button.ino").write_text(original_code)
        
        issue_title = "Fix button pin configuration"
        issue_body = """
Button on pin 2 is not working because pinMode is not set.
Need to add pinMode(BUTTON_PIN, INPUT_PULLUP) in setup().
"""
        
        print(f"Issue: {issue_title}")
        print(f"原始代码:\n{original_code}")
        
        # 分析
        analyzer = CodeAnalyzer()
        files, graph, reasoning = analyzer.analyze_for_issue(
            repo, issue_title, issue_body
        )
        
        print(f"\n分析结果:")
        print(f"  建议修改文件: {files}")
        
        pins = graph.files['button.ino'].pins
        print(f"  检测到的引脚:")
        for pin_num, pin_info in pins.items():
            print(f"    引脚 {pin_num}: mode={pin_info.mode}, ops={pin_info.operations}")
        
        assert 'button.ino' in files
        
        # 检测 BUTTON_PIN (2) 的配置问题
        # 当前代码没有 pinMode for BUTTON_PIN
        
        # 模拟修复
        modified_code = """#include <Wire.h>

#define BUTTON_PIN 2
#define LED_PIN 13

void setup() {
    Serial.begin(9600);
    // Configure button with internal pullup
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
}

void loop() {
    int buttonState = digitalRead(BUTTON_PIN);
    // Note: INPUT_PULLUP means LOW when pressed
    if (buttonState == LOW) {
        digitalWrite(LED_PIN, HIGH);
    } else {
        digitalWrite(LED_PIN, LOW);
    }
}
"""
        
        print(f"\n修改后代码:\n{modified_code}")
        
        # 验证
        validator = ChangeValidator()
        result = validator.validate_modification(
            "button.ino", original_code, modified_code, issue_body
        )
        
        print(f"\n验证结果:")
        print(f"  有效: {result.is_valid}")
        print(f"  警告: {result.warnings}")
        
        assert result.is_valid
        assert "INPUT_PULLUP" in modified_code
        assert "buttonState == LOW" in modified_code
        
        print("\n✅ 场景3测试通过！")
        return True


def main():
    print("\n" + "="*60)
    print("端到端场景测试")
    print("="*60)
    
    results = []
    
    try:
        results.append(("场景1: 传感器滤波", test_scenario_1_sensor_filtering()))
    except Exception as e:
        print(f"\n❌ 场景1失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("场景1: 传感器滤波", False))
    
    try:
        results.append(("场景2: 错误处理", test_scenario_2_error_handling()))
    except Exception as e:
        print(f"\n❌ 场景2失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("场景2: 错误处理", False))
    
    try:
        results.append(("场景3: 引脚配置", test_scenario_3_pin_config_fix()))
    except Exception as e:
        print(f"\n❌ 场景3失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("场景3: 引脚配置", False))
    
    # 总结
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    passed_count = sum(1 for _, p in results if p)
    total = len(results)
    
    print(f"\n总计: {passed_count}/{total} 通过")
    
    if passed_count == total:
        print("\n🎉 所有端到端场景测试通过！")
        return 0
    else:
        print(f"\n⚠️ {total - passed_count} 个场景失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
