#!/usr/bin/env python3
"""
成功案例存储测试

测试内容：
1. 案例创建和保存
2. 案例加载
3. 相似案例检索
4. 从执行结果创建案例
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_base.success_case_store import (
    SuccessCaseStore, SuccessCase, IssueInfo, SolutionInfo, 
    OutcomeInfo, FileModification, CodePattern
)


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


def test_case_creation():
    """测试案例创建"""
    print_header("测试 1: 案例创建")
    
    passed = 0
    failed = 0
    
    # 测试 1.1: 创建基本案例
    print("\n1.1 创建基本案例")
    try:
        case = SuccessCase(
            repository="test/arduino-project",
            issue=IssueInfo(
                title="Fix analogRead noise on A0",
                body="The sensor readings are very noisy, need filtering",
                keywords=["analogRead", "A0", "noise", "filter"],
                language="arduino",
                complexity="simple"
            ),
            solution=SolutionInfo(
                description="Add moving average filter",
                approach="filter"
            ),
            outcome=OutcomeInfo(success=True, pr_merged=True)
        )
        
        if case.case_id and case.repository == "test/arduino-project":
            print_result("案例创建", True)
            passed += 1
        else:
            print_result("案例创建", False, "属性不匹配")
            failed += 1
            
    except Exception as e:
        print_result("案例创建", False, str(e))
        failed += 1
    
    # 测试 1.2: 转换为字典
    print("\n1.2 序列化为字典")
    try:
        case_dict = case.to_dict()
        
        if (case_dict['repository'] == "test/arduino-project" and
            case_dict['issue']['title'] == "Fix analogRead noise on A0" and
            case_dict['solution']['approach'] == "filter"):
            print_result("序列化", True)
            passed += 1
        else:
            print_result("序列化", False, "字典内容不匹配")
            failed += 1
            
    except Exception as e:
        print_result("序列化", False, str(e))
        failed += 1
    
    # 测试 1.3: 从字典恢复
    print("\n1.3 从字典恢复")
    try:
        restored = SuccessCase.from_dict(case_dict)
        
        if (restored.case_id == case.case_id and
            restored.issue.title == case.issue.title):
            print_result("反序列化", True)
            passed += 1
        else:
            print_result("反序列化", False, "恢复后内容不匹配")
            failed += 1
            
    except Exception as e:
        print_result("反序列化", False, str(e))
        failed += 1
    
    return passed, failed


def test_case_storage():
    """测试案例存储"""
    print_header("测试 2: 案例存储")
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SuccessCaseStore(Path(tmpdir))
        
        # 测试 2.1: 保存案例
        print("\n2.1 保存案例")
        try:
            case = SuccessCase(
                repository="test/repo",
                issue=IssueInfo(
                    title="Test Issue",
                    body="Test body",
                    language="python"
                ),
                solution=SolutionInfo(description="Test fix", approach="fix"),
                outcome=OutcomeInfo(success=True)
            )
            
            case_id = store.save_case(case)
            
            if case_id and Path(tmpdir).exists():
                print_result("保存案例", True, f"ID: {case_id}")
                passed += 1
            else:
                print_result("保存案例", False)
                failed += 1
                
        except Exception as e:
            print_result("保存案例", False, str(e))
            failed += 1
        
        # 测试 2.2: 加载案例
        print("\n2.2 加载案例")
        try:
            loaded = store.load_case(case_id)
            
            if loaded and loaded.case_id == case_id:
                print_result("加载案例", True)
                passed += 1
            else:
                print_result("加载案例", False, "加载失败或ID不匹配")
                failed += 1
                
        except Exception as e:
            print_result("加载案例", False, str(e))
            failed += 1
        
        # 测试 2.3: 加载不存在的案例
        print("\n2.3 加载不存在的案例")
        try:
            not_found = store.load_case("non_existent_case")
            
            if not_found is None:
                print_result("正确处理缺失案例", True)
                passed += 1
            else:
                print_result("正确处理缺失案例", False, "应返回None")
                failed += 1
                
        except Exception as e:
            print_result("正确处理缺失案例", False, str(e))
            failed += 1

    return passed, failed


def test_case_from_execution():
    """测试从执行结果创建案例"""
    print_header("测试 3: 从执行结果创建案例")
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SuccessCaseStore(Path(tmpdir))
        
        # 模拟执行结果
        original_contents = {
            "sensor.ino": """
void setup() {
    Serial.begin(9600);
}
void loop() {
    int value = analogRead(A0);
    Serial.println(value);
}
"""
        }
        
        modified_contents = {
            "sensor.ino": """
void setup() {
    Serial.begin(9600);
}
void loop() {
    int filtered = getFilteredValue(A0);
    Serial.println(filtered);
}
"""
        }
        
        print("\n3.1 创建 Arduino 案例")
        try:
            case = store.create_case_from_execution(
                repo="owner/arduino-project",
                issue_number=42,
                issue_title="Fix analogRead noise on A0",
                issue_body="The sensor readings are very noisy, need filtering",
                files_modified=["sensor.ino"],
                original_contents=original_contents,
                modified_contents=modified_contents,
                success=True
            )
            
            if (case.repository == "owner/arduino-project" and
                case.issue.language == "arduino" and
                len(case.solution.files_modified) == 1):
                print_result("创建 Arduino 案例", True)
                print(f"   检测到的关键词: {case.issue.keywords}")
                passed += 1
            else:
                print_result("创建 Arduino 案例", False, "属性不匹配")
                failed += 1
                
        except Exception as e:
            print_result("创建 Arduino 案例", False, str(e))
            import traceback
            traceback.print_exc()
            failed += 1
        
        print("\n3.2 保存执行案例")
        try:
            case_id = store.save_case(case)
            loaded = store.load_case(case_id)
            
            if loaded and loaded.outcome.success:
                print_result("保存执行案例", True, f"ID: {case_id}")
                passed += 1
            else:
                print_result("保存执行案例", False)
                failed += 1
                
        except Exception as e:
            print_result("保存执行案例", False, str(e))
            failed += 1

    return passed, failed


def test_index_management():
    """测试索引管理"""
    print_header("测试 4: 索引管理")
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SuccessCaseStore(Path(tmpdir))
        
        # 创建多个案例
        for i in range(3):
            case = SuccessCase(
                repository=f"test/repo{i}",
                issue=IssueInfo(title=f"Issue {i}", body=f"Body {i}"),
                solution=SolutionInfo(description=f"Fix {i}", approach="fix"),
                outcome=OutcomeInfo(success=True)
            )
            store.save_case(case)
        
        print("\n4.1 获取所有案例")
        try:
            cases = store.get_all_cases()
            
            if len(cases) == 3:
                print_result("获取所有案例", True, f"数量: {len(cases)}")
                passed += 1
            else:
                print_result("获取所有案例", False, f"期望3个，实际{len(cases)}")
                failed += 1
                
        except Exception as e:
            print_result("获取所有案例", False, str(e))
            failed += 1
        
        print("\n4.2 按语言过滤")
        try:
            # 创建一个 Python 案例
            py_case = SuccessCase(
                repository="test/python-repo",
                issue=IssueInfo(title="Python Issue", body="Body", language="python"),
                solution=SolutionInfo(description="Python fix", approach="fix"),
                outcome=OutcomeInfo(success=True)
            )
            store.save_case(py_case)
            
            python_cases = store.get_all_cases(language="python")
            
            if len(python_cases) == 1:
                print_result("按语言过滤", True)
                passed += 1
            else:
                print_result("按语言过滤", False, f"期望1个，实际{len(python_cases)}")
                failed += 1
                
        except Exception as e:
            print_result("按语言过滤", False, str(e))
            failed += 1

    return passed, failed


def main():
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}成功案例存储测试{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    
    total_passed = 0
    total_failed = 0
    
    try:
        p, f = test_case_creation()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"{Colors.RED}案例创建测试异常: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        total_failed += 3
    
    try:
        p, f = test_case_storage()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"{Colors.RED}案例存储测试异常: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        total_failed += 3
    
    try:
        p, f = test_case_from_execution()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"{Colors.RED}执行案例测试异常: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        total_failed += 2
    
    try:
        p, f = test_index_management()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"{Colors.RED}索引管理测试异常: {e}{Colors.END}")
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
        print(f"\n{Colors.GREEN}🎉 所有测试通过！案例存储功能正常！{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.YELLOW}⚠️ 有 {total_failed} 项测试失败，请检查{Colors.END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
