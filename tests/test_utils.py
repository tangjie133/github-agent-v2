#!/usr/bin/env python3
"""
工具模块测试
"""

import pytest
from unittest.mock import Mock, patch

from utils import retry, RetryableError, AgentError, GitHubAPIError


class TestRetry:
    """测试重试机制"""
    
    def test_success_no_retry(self):
        """测试成功时不重试"""
        mock_func = Mock(return_value="success")
        
        @retry(max_retries=3)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_on_exception(self):
        """测试异常时重试"""
        mock_func = Mock(side_effect=[Exception("error"), "success"])
        
        @retry(max_retries=3, delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_max_retries_exceeded(self):
        """测试超过最大重试次数"""
        from utils.retry import MaxRetriesExceeded
        
        mock_func = Mock(side_effect=Exception("persistent error"))
        
        @retry(max_retries=2, delay=0.01)
        def test_func():
            return mock_func()
        
        with pytest.raises(MaxRetriesExceeded):
            test_func()
        
        assert mock_func.call_count == 3  # 初始 + 2次重试
    
    def test_specific_exception_only(self):
        """测试只重试特定异常"""
        mock_func = Mock(side_effect=ValueError("value error"))
        
        @retry(max_retries=2, delay=0.01, exceptions=(TypeError,))
        def test_func():
            return mock_func()
        
        with pytest.raises(ValueError):
            test_func()
        
        assert mock_func.call_count == 1  # 不重试
    
    def test_retry_callbacks(self):
        """测试重试回调函数"""
        on_retry = Mock()
        on_success = Mock()
        
        mock_func = Mock(side_effect=[Exception("error"), "success"])
        
        @retry(max_retries=3, delay=0.01, on_retry=on_retry, on_success=on_success)
        def test_func():
            return mock_func()
        
        test_func()
        
        assert on_retry.called
        assert on_success.called


class TestErrors:
    """测试错误类"""
    
    def test_agent_error(self):
        """测试基础错误"""
        error = AgentError("Test error", code="TEST_ERROR", details={"key": "value"})
        
        assert error.message == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.details == {"key": "value"}
        assert "TEST_ERROR" in str(error)
    
    def test_github_api_error(self):
        """测试 GitHub API 错误"""
        error = GitHubAPIError(
            "API failed",
            status_code=404,
            response={"message": "Not found"}
        )
        
        assert error.status_code == 404
        assert error.code == "GITHUB_API_ERROR"
        assert error.response["message"] == "Not found"
    
    def test_code_execution_error(self):
        """测试代码执行错误"""
        error = CodeExecutionError(
            "Syntax error",
            file_path="test.py",
            error_output="Invalid syntax"
        )
        
        assert error.file_path == "test.py"
        assert error.error_output == "Invalid syntax"


# 导入 CodeExecutionError
from utils import CodeExecutionError
