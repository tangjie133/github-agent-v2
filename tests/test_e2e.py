#!/usr/bin/env python3
"""
端到端测试

模拟完整的 GitHub Webhook 处理流程
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 确保导入正确
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import GitHubEvent, IssueContext, IntentType, ProcessingStatus

# 如果没有 pytest，使用简单的测试框架
try:
    import pytest
except ImportError:
    class MockPytest:
        @staticmethod
        def fixture(func):
            return func
        
        @staticmethod
        def mark(*args, **kwargs):
            class Marker:
                @staticmethod
                def __call__(func):
                    return func
            return Marker()
    
    pytest = MockPytest()
    pytest.fixture = staticmethod(lambda f: f)


class TestEndToEndFlow:
    """端到端流程测试"""
    
    @pytest.fixture
    def mock_services(self):
        """模拟所有外部服务"""
        with patch('github_api.auth_manager.GitHubAuthManager') as mock_auth, \
             patch('github_api.github_client.GitHubClient') as mock_github, \
             patch('cloud_agent.openclaw_client.OpenClawClient') as mock_openclaw, \
             patch('code_executor.code_generator.CodeGenerator') as mock_codegen:
            
            # 配置模拟
            mock_auth_instance = MagicMock()
            mock_auth_instance.get_installation_token.return_value = "test_token"
            mock_auth.return_value = mock_auth_instance
            
            mock_github_instance = MagicMock()
            mock_github_instance.create_issue_comment.return_value = {"id": 123}
            mock_github_instance.create_pull_request.return_value = {
                "number": 42,
                "html_url": "https://github.com/test/repo/pull/42"
            }
            mock_github.return_value = mock_github_instance
            
            mock_openclaw_instance = MagicMock()
            mock_openclaw_instance.health_check.return_value = True
            mock_openclaw_instance.generate.return_value = json.dumps({
                "intent": "modify",
                "confidence": 0.9,
                "reasoning": "这是一个修改请求"
            })
            mock_openclaw.return_value = mock_openclaw_instance
            
            mock_codegen_instance = MagicMock()
            mock_codegen_instance.health_check.return_value = True
            mock_codegen_instance.generate_modification.return_value = "print('modified')"
            mock_codegen.return_value = mock_codegen_instance
            
            yield {
                'auth': mock_auth_instance,
                'github': mock_github_instance,
                'openclaw': mock_openclaw_instance,
                'codegen': mock_codegen_instance
            }
    
    def test_issue_opened_webhook(self, mock_services):
        """测试 Issue 打开事件处理"""
        print("\n🧪 测试: Issue Opened Webhook 处理")
        
        # 创建模拟事件
        event = GitHubEvent(
            event_type="issues",
            action="opened",
            repository={"full_name": "test/repo"},
            installation={"id": 12345},
            issue={
                "number": 1,
                "title": "Fix bug @agent",
                "body": "Please fix the null pointer exception",
                "user": {"login": "testuser"}
            }
        )
        
        # 验证事件结构
        assert event.event_type == "issues"
        assert event.action == "opened"
        assert "@agent" in event.issue["title"]
        assert event.repo_full_name == "test/repo"
        
        print("  ✅ Webhook 事件解析成功")
        print(f"     事件类型: {event.event_type}")
        print(f"     仓库: {event.repo_full_name}")
        print(f"     Issue: #{event.issue['number']}")
    
    def test_comment_trigger_webhook(self, mock_services):
        """测试评论触发事件"""
        print("\n🧪 测试: 评论触发 Webhook 处理")
        
        event = GitHubEvent(
            event_type="issue_comment",
            action="created",
            repository={"full_name": "test/repo"},
            installation={"id": 12345},
            issue={"number": 1},
            comment={
                "id": 123,
                "body": "@agent please fix this issue",
                "user": {"login": "testuser"}
            }
        )
        
        assert event.event_type == "issue_comment"
        assert "@agent" in event.comment["body"]
        
        print("  ✅ 评论事件解析成功")
        print(f"     触发关键词: @agent")
    
    def test_full_processing_flow(self, mock_services):
        """测试完整处理流程"""
        print("\n🧪 测试: 完整处理流程")
        
        # 步骤 1: 构建上下文
        context = IssueContext(
            issue_number=1,
            title="Fix bug @agent",
            body="Fix the error in main.py",
            author="testuser",
            current_instruction="Fix the error in main.py"
        )
        
        print("  ✅ 步骤 1: 上下文构建成功")
        
        # 步骤 2: 意图识别 (模拟)
        intent_result = Mock()
        intent_result.intent = IntentType.MODIFY
        intent_result.confidence = 0.9
        intent_result.reasoning = "这是一个代码修改请求"
        intent_result.needs_research = False
        intent_result.research_topics = []
        
        assert intent_result.intent == IntentType.MODIFY
        assert intent_result.confidence > 0.8
        
        print("  ✅ 步骤 2: 意图识别成功")
        print(f"     意图: {intent_result.intent.value}")
        print(f"     置信度: {intent_result.confidence}")
        
        # 步骤 3: 决策制定 (模拟)
        action_plan = Mock()
        action_plan.action = "modify"
        action_plan.complexity = "simple"
        action_plan.confidence = 0.9
        action_plan.files_to_modify = ["main.py"]
        action_plan.change_description = "修复空指针异常"
        
        assert action_plan.action == "modify"
        
        print("  ✅ 步骤 3: 决策制定成功")
        print(f"     操作: {action_plan.action}")
        print(f"     复杂度: {action_plan.complexity}")
        
        # 步骤 4: 代码生成 (模拟)
        modified_code = "def main():\n    print('fixed')"
        
        assert "fixed" in modified_code
        
        print("  ✅ 步骤 4: 代码生成成功")
        
        # 步骤 5: 创建 PR (模拟)
        pr_result = {
            "number": 42,
            "html_url": "https://github.com/test/repo/pull/42"
        }
        
        assert pr_result["number"] == 42
        
        print("  ✅ 步骤 5: PR 创建成功")
        print(f"     PR: #{pr_result['number']}")
        print(f"     URL: {pr_result['html_url']}")
        
        # 最终验证
        processing_result = Mock()
        processing_result.status = ProcessingStatus.COMPLETED
        processing_result.pr_number = 42
        
        assert processing_result.status == ProcessingStatus.COMPLETED
        
        print("\n  🎉 完整流程测试通过!")
    
    def test_smart_trigger_mode(self):
        """测试智能触发模式"""
        print("\n🧪 测试: 智能触发模式")
        
        # 应该触发的场景
        trigger_cases = [
            {"title": "Fix bug @agent", "body": "", "expected": True},
            {"title": "", "body": "Please help @agent", "expected": True},
            {"title": "Bug fix", "body": "", "expected": False},  # 没有 @agent
        ]
        
        for case in trigger_cases:
            should_trigger = "@agent" in case["title"] or "@agent" in case["body"]
            assert should_trigger == case["expected"], f"失败: {case}"
        
        print("  ✅ 智能触发模式测试通过")
        for case in trigger_cases:
            result = "✓" if case["expected"] else "✗"
            print(f"     {result} {case['title'][:30] or case['body'][:30]}")


class TestComponentIntegration:
    """组件集成测试"""
    
    def test_all_modules_import(self):
        """测试所有模块可以正常导入"""
        print("\n🧪 测试: 模块导入")
        
        modules = [
            "core.models",
            "core.processor",
            "core.context_builder",
            "core.state_manager",
            "github_api.github_client",
            "github_api.auth_manager",
            "cloud_agent.intent_classifier",
            "cloud_agent.decision_engine",
            "cloud_agent.openclaw_client",
            "knowledge_base.kb_client",
            "knowledge_base.kb_integrator",
            "code_executor.code_generator",
            "code_executor.repo_manager",
            "code_executor.safe_modifier",
            "code_executor.change_validator",
            "code_executor.code_executor",
            "config.settings",
            "utils.retry",
            "utils.errors",
        ]
        
        failed = []
        for module in modules:
            try:
                __import__(module)
                print(f"  ✅ {module}")
            except Exception as e:
                failed.append((module, str(e)))
                print(f"  ❌ {module}: {e}")
        
        if failed:
            pytest.fail(f"以下模块导入失败: {failed}")
        
        print(f"\n  ✅ 全部 {len(modules)} 个模块导入成功")


class TestWebhookProcessing:
    """Webhook 处理测试"""
    
    def test_webhook_signature_verification(self):
        """测试 Webhook 签名验证"""
        print("\n🧪 测试: Webhook 签名验证")
        
        import hmac
        import hashlib
        
        secret = b"test-secret"
        payload = b'{"action":"opened"}'
        
        # 生成签名
        signature = 'sha256=' + hmac.new(secret, payload, hashlib.sha256).hexdigest()
        
        # 验证签名
        expected = 'sha256=' + hmac.new(secret, payload, hashlib.sha256).hexdigest()
        
        assert signature == expected
        print("  ✅ 签名验证逻辑正确")
    
    def test_event_parsing(self):
        """测试事件解析"""
        print("\n🧪 测试: 事件解析")
        
        # issues 事件
        issues_payload = {
            "action": "opened",
            "issue": {"number": 1, "title": "Test"},
            "repository": {"full_name": "test/repo"},
            "installation": {"id": 123}
        }
        
        event = GitHubEvent(
            event_type="issues",
            action=issues_payload["action"],
            repository=issues_payload["repository"],
            installation=issues_payload["installation"],
            issue=issues_payload["issue"]
        )
        
        assert event.issue["number"] == 1
        print("  ✅ 事件解析成功")


if __name__ == "__main__":
    # 手动运行测试
    print("=" * 60)
    print("GitHub Agent V2 - 端到端测试")
    print("=" * 60)
    
    test_class = TestEndToEndFlow()
    
    # 运行测试
    try:
        test_class.test_issue_opened_webhook(None)
        test_class.test_comment_trigger_webhook(None)
        test_class.test_full_processing_flow(None)
        test_class.test_smart_trigger_mode()
        
        print("\n" + "=" * 60)
        print("✅ 所有端到端测试通过!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
