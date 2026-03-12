#!/usr/bin/env python3
"""
Pytest 配置和共享 fixtures
"""

import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def test_data_dir():
    """测试数据目录"""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture
def temp_work_dir(tmp_path):
    """临时工作目录"""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    return work_dir


@pytest.fixture
def mock_env_vars(monkeypatch):
    """设置测试环境变量"""
    env_vars = {
        "GITHUB_APP_ID": "123456",
        "GITHUB_WEBHOOK_SECRET": "test-secret",
        "OLLAMA_MODEL": "test-model",
        "OLLAMA_HOST": "http://localhost:11434",
        "OPENCLAW_URL": "http://localhost:3000",
        "KB_SERVICE_URL": "http://localhost:8000",
        "GITHUB_AGENT_WORKDIR": "/tmp/test-agent",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def sample_issue_context():
    """示例 Issue 上下文"""
    from core.models import IssueContext
    
    return IssueContext(
        issue_number=1,
        title="Test Issue",
        body="This is a test issue description",
        author="testuser",
        current_instruction="Fix the bug"
    )


@pytest.fixture
def sample_github_event():
    """示例 GitHub Webhook 事件"""
    from core.models import GitHubEvent
    
    return GitHubEvent(
        event_type="issues",
        action="opened",
        repo_full_name="test/repo",
        installation_id=12345,
        issue={
            "number": 1,
            "title": "Test Issue",
            "body": "Test body @agent",
            "user": {"login": "testuser"}
        }
    )
