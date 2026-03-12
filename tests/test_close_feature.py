#!/usr/bin/env python3
"""
Test script for issue close feature
"""

import sys
sys.path.insert(0, '/home/tj/.npm-global/lib/node_modules/openclaw/skills/github-agent-v2')

from core.models import IssueContext, GitHubEvent
from core.issue_followup import IssueFollowupManager


def test_should_process_close_keywords():
    """Test that _should_process recognizes close keywords"""
    from core.processor import IssueProcessor
    
    processor = IssueProcessor()
    
    # Test cases that should trigger processing (close keywords)
    test_cases_should_process = [
        ("issue_comment", {"body": "已解决"}, True),
        ("issue_comment", {"body": "搞定了"}, True),
        ("issue_comment", {"body": "可以关闭"}, True),
        ("issue_comment", {"body": "ok了"}, True),
        ("issue_comment", {"body": "fixed"}, True),
        ("issue_comment", {"body": "resolved"}, True),
        ("issue_comment", {"body": "测试通过"}, True),
        ("issue_comment", {"body": "完美"}, True),
    ]
    
    # Test cases that should NOT trigger processing (no close keywords, no @agent)
    test_cases_should_not_process = [
        ("issue_comment", {"body": "这是一个普通评论"}, False),
        ("issue_comment", {"body": "请帮我修改代码"}, False),  # 需要 @agent
        ("issue_comment", {"body": "hello world"}, False),
    ]
    
    print("=" * 60)
    print("Testing _should_process with close keywords")
    print("=" * 60)
    
    all_passed = True
    
    for event_type, comment, expected in test_cases_should_process:
        event = GitHubEvent(
            event_type=event_type,
            action="created",
            repository={"full_name": "test/repo"},
            comment=comment
        )
        result = processor._should_process(event)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        if result != expected:
            all_passed = False
        print(f"{status} '{comment['body'][:20]}...' -> {result} (expected {expected})")
    
    for event_type, comment, expected in test_cases_should_not_process:
        event = GitHubEvent(
            event_type=event_type,
            action="created",
            repository={"full_name": "test/repo"},
            comment=comment
        )
        result = processor._should_process(event)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        if result != expected:
            all_passed = False
        print(f"{status} '{comment['body'][:20]}...' -> {result} (expected {expected})")
    
    return all_passed


def test_check_resolution_keywords():
    """Test check_resolution_keywords function"""
    manager = IssueFollowupManager()
    
    test_cases = [
        ("已解决", True),
        ("解决了", True),
        ("搞定", True),
        ("可以关闭", True),
        ("fixed", True),
        ("resolved", True),
        ("works", True),
        ("测试通过", True),
        ("完美", True),
        ("ok了", True),
        ("没解决", False),  # NOT resolved
        ("还不行", False),  # NOT resolved
        ("仍然报错", False),  # NOT resolved
        ("not working", False),  # NOT resolved
        ("请帮我修改", None),  # New request, unclear
        ("如何实现的", None),  # New request, unclear
    ]
    
    print()
    print("=" * 60)
    print("Testing check_resolution_keywords")
    print("=" * 60)
    
    all_passed = True
    
    for text, expected in test_cases:
        result = manager.check_resolution_keywords(text)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        if result != expected:
            all_passed = False
        print(f"{status} '{text}' -> {result} (expected {expected})")
    
    return all_passed


def test_check_close_keywords():
    """Test _check_close_keywords function"""
    from core.processor import IssueProcessor
    
    processor = IssueProcessor()
    
    test_cases = [
        ("已解决", True),
        ("解决了", True),
        ("搞定", True),
        ("可以关闭", True),
        ("fixed", True),
        ("resolved", True),
        ("works", True),
        ("测试通过", True),
        ("完美", True),
        ("谢谢", True),
        ("it works", True),
        ("completed", True),
        ("普通评论", False),
        ("", False),
    ]
    
    print()
    print("=" * 60)
    print("Testing _check_close_keywords (fallback detection)")
    print("=" * 60)
    
    all_passed = True
    
    for text, expected in test_cases:
        result = processor._check_close_keywords(text)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        if result != expected:
            all_passed = False
        print(f"{status} '{text}' -> {result} (expected {expected})")
    
    return all_passed


if __name__ == "__main__":
    print("\n🧪 Testing Issue Close Feature\n")
    
    results = []
    results.append(("_should_process", test_should_process_close_keywords()))
    results.append(("check_resolution_keywords", test_check_resolution_keywords()))
    results.append(("_check_close_keywords", test_check_close_keywords()))
    
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print()
    if all_passed:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed")
        sys.exit(1)
