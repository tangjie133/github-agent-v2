#!/usr/bin/env python3
"""
Phase 1 实际效果测试

模拟真实的代码修改流程，验证案例是否正确保存到知识库
"""

import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

# 设置日志级别
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from knowledge_base.success_case_store import (
    SuccessCaseStore, SuccessCase, 
    IssueInfo, SolutionInfo, OutcomeInfo
)


def print_section(title):
    print("\n" + "="*70)
    print(f"📋 {title}")
    print("="*70)


def print_success(msg):
    print(f"✅ {msg}")


def print_info(msg):
    print(f"ℹ️  {msg}")


def print_error(msg):
    print(f"❌ {msg}")


def simulate_code_execution(store: SuccessCaseStore):
    """
    模拟代码修改执行流程
    
    场景: 修复 Arduino A0 引脚的传感器噪声问题
    """
    print_section("模拟场景: Arduino 传感器滤波修复")
    
    # 1. 模拟 Issue 信息
    issue_title = "Fix analogRead noise on A0 sensor"
    issue_body = """
The temperature sensor connected to analog pin A0 is giving very noisy readings.
Values jump around ±50 units even when temperature is stable.

Need to add some kind of filtering to smooth the readings.

Hardware:
- Arduino Uno
- LM35 temperature sensor on A0
- Using Wire library for I2C display
"""
    
    print_info("Issue 信息:")
    print(f"   标题: {issue_title}")
    print(f"   内容长度: {len(issue_body)} 字符")
    
    # 2. 模拟原始代码
    original_code = """#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define SENSOR_PIN A0
#define LED_PIN 13

LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
    Serial.begin(9600);
    pinMode(SENSOR_PIN, INPUT);
    pinMode(LED_PIN, OUTPUT);
    Wire.begin();
    lcd.init();
    lcd.backlight();
}

void loop() {
    // Read raw sensor value
    int rawValue = analogRead(SENSOR_PIN);
    
    // Convert to temperature
    float voltage = rawValue * 5.0 / 1023.0;
    float temperature = voltage * 100;
    
    // Display
    Serial.print("Temperature: ");
    Serial.println(temperature);
    
    lcd.setCursor(0, 0);
    lcd.print("Temp: ");
    lcd.print(temperature);
    lcd.print(" C  ");
    
    delay(1000);
}
"""
    
    # 3. 模拟修改后的代码
    modified_code = """#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define SENSOR_PIN A0
#define LED_PIN 13

// Moving average filter
#define FILTER_SIZE 10
int readings[FILTER_SIZE];
int readIndex = 0;
int total = 0;
int average = 0;

LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
    Serial.begin(9600);
    pinMode(SENSOR_PIN, INPUT);
    pinMode(LED_PIN, OUTPUT);
    Wire.begin();
    lcd.init();
    lcd.backlight();
    
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
    
    // Convert to temperature
    float voltage = average * 5.0 / 1023.0;
    float temperature = voltage * 100;
    
    // Display
    Serial.print("Temperature: ");
    Serial.println(temperature);
    
    lcd.setCursor(0, 0);
    lcd.print("Temp: ");
    lcd.print(temperature);
    lcd.print(" C  ");
    
    delay(1000);
}
"""
    
    print_info("代码修改:")
    print(f"   文件: sensor.ino")
    print(f"   原始代码: {len(original_code)} 字符")
    print(f"   修改后: {len(modified_code)} 字符 (+{len(modified_code) - len(original_code)})")
    print(f"   主要变更: 添加了移动平均滤波器 (FILTER_SIZE=10)")
    
    # 4. 使用 CodeExecutor 的方式创建案例
    print_section("创建成功案例")
    
    case = store.create_case_from_execution(
        repo="owner/arduino-temperature-monitor",
        issue_number=42,
        issue_title=issue_title,
        issue_body=issue_body,
        files_modified=["sensor.ino"],
        original_contents={"sensor.ino": original_code},
        modified_contents={"sensor.ino": modified_code},
        success=True
    )
    
    # 模拟 PR 信息
    case.outcome.pr_number = 43
    case.outcome.pr_merged = True
    case.outcome.user_feedback = "positive"
    
    print_info("案例信息:")
    print(f"   案例ID: {case.case_id}")
    print(f"   仓库: {case.repository}")
    print(f"   语言: {case.issue.language}")
    print(f"   复杂度: {case.issue.complexity}")
    print(f"   关键词: {case.issue.keywords}")
    print(f"   检测到的引脚: {case.solution.arduino_specific.pins_involved if case.solution.arduino_specific else 'N/A'}")
    print(f"   使用的库: {case.solution.arduino_specific.libraries_used if case.solution.arduino_specific else 'N/A'}")
    
    return case


def test_case_storage():
    """测试案例存储功能"""
    print_section("Phase 1 效果测试")
    
    # 1. 创建临时存储目录
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "test_cases"
        storage_path.mkdir()
        
        print_info(f"知识库存储路径: {storage_path}")
        
        # 2. 创建存储管理器
        store = SuccessCaseStore(storage_path)
        
        # 3. 模拟执行并创建案例
        case = simulate_code_execution(store)
        
        # 4. 保存案例
        print_section("保存案例到知识库")
        case_id = store.save_case(case)
        print_success(f"案例已保存: {case_id}")
        
        # 5. 验证文件创建
        print_section("验证存储结果")
        
        # 检查索引文件
        index_file = storage_path / "index.json"
        if index_file.exists():
            with open(index_file) as f:
                index = json.load(f)
            print_success(f"索引文件已创建: {index_file}")
            print_info(f"   总案例数: {index.get('total_cases', 0)}")
            print_info(f"   最后更新: {index.get('last_updated', 'N/A')}")
        else:
            print_error("索引文件未创建")
        
        # 查找案例文件
        case_files = list(storage_path.rglob(f"{case_id}.json"))
        if case_files:
            case_file = case_files[0]
            print_success(f"案例文件已创建: {case_file}")
            print_info(f"   文件大小: {case_file.stat().st_size} 字节")
            
            # 显示文件内容预览
            with open(case_file) as f:
                data = json.load(f)
            print_info(f"   Schema 版本: {data.get('schema_version')}")
            print_info(f"   Issue 标题: {data['issue']['title'][:50]}...")
            print_info(f"   解决方案: {data['solution']['description']}")
            print_info(f"   修改文件数: {len(data['solution']['files_modified'])}")
            print_info(f"   PR 状态: {'已合并' if data['outcome']['pr_merged'] else '未合并'}")
        else:
            print_error("案例文件未找到")
        
        # 6. 测试案例加载
        print_section("测试案例加载")
        loaded_case = store.load_case(case_id)
        
        if loaded_case:
            print_success(f"案例加载成功: {loaded_case.case_id}")
            print_info(f"   仓库: {loaded_case.repository}")
            print_info(f"   成功状态: {loaded_case.outcome.success}")
            
            # 显示摘要
            print("\n📄 案例摘要:")
            print("-" * 70)
            print(loaded_case.get_summary())
            print("-" * 70)
        else:
            print_error("案例加载失败")
        
        # 7. 测试案例检索（如果有多个案例）
        print_section("测试案例检索")
        
        # 创建第二个案例
        case2 = SuccessCase(
            repository="owner/another-project",
            issue=IssueInfo(
                title="Add button debounce for pin 2",
                body="Button on digital pin 2 is bouncing",
                keywords=["button", "debounce", "pin2"],
                language="arduino"
            ),
            solution=SolutionInfo(
                description="Add software debounce",
                approach="fix"
            ),
            outcome=OutcomeInfo(success=True)
        )
        case2_id = store.save_case(case2)
        print_info(f"创建第二个案例: {case2_id}")
        
        # 获取所有案例
        all_cases = store.get_all_cases()
        print_success(f"检索到 {len(all_cases)} 个案例")
        
        # 按语言过滤
        arduino_cases = store.get_all_cases(language="arduino")
        print_info(f"Arduino 案例: {len(arduino_cases)} 个")
        
        # 显示存储结构
        print_section("知识库存储结构")
        
        def show_tree(path, prefix=""):
            items = sorted(path.iterdir())
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                
                if item.is_dir():
                    print(f"{prefix}{connector}{item.name}/")
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    show_tree(item, new_prefix)
                else:
                    size = item.stat().st_size
                    print(f"{prefix}{connector}{item.name} ({size} bytes)")
        
        print(f"{storage_path}/")
        show_tree(storage_path, "")
        
        # 8. 总结
        print_section("Phase 1 测试结果总结")
        
        checks = [
            ("案例存储目录创建", storage_path.exists()),
            ("索引文件创建", (storage_path / "index.json").exists()),
            ("案例文件创建", len(case_files) > 0),
            ("案例可加载", loaded_case is not None),
            ("案例数据完整", loaded_case and loaded_case.case_id == case_id),
            ("多案例支持", len(all_cases) == 2),
            ("语言过滤", len(arduino_cases) == 2),
        ]
        
        passed = sum(1 for _, result in checks if result)
        total = len(checks)
        
        for check_name, result in checks:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{status} - {check_name}")
        
        print(f"\n📊 总体: {passed}/{total} 项检查通过 ({passed/total*100:.0f}%)")
        
        if passed == total:
            print("\n🎉 Phase 1 测试全部通过！成功案例存储功能正常工作！")
            print("\n下一步:")
            print("  - 案例已保存到本地知识库")
            print("  - 可以继续 Phase 2: 推送到资料仓库")
            return True
        else:
            print("\n⚠️ 部分检查未通过，请查看详细日志")
            return False


def main():
    """主函数"""
    print("\n" + "="*70)
    print("🔬 Phase 1 实际效果测试")
    print("   测试目标: 验证成功案例存储功能")
    print("="*70)
    
    try:
        success = test_case_storage()
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
