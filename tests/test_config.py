#!/usr/bin/env python3
"""
配置模块测试
"""

import pytest
from config import get_settings, reload_settings, print_settings


class TestSettings:
    """测试配置类"""
    
    def test_default_values(self, mock_env_vars):
        """测试默认值"""
        settings = get_settings()
        
        assert settings.github_agent_port == 8080
        assert settings.github_agent_host == "0.0.0.0"
        assert settings.agent_confirm_mode == "auto"
        assert settings.agent_auto_confirm_threshold == 0.8
    
    def test_env_override(self, monkeypatch):
        """测试环境变量覆盖"""
        monkeypatch.setenv("GITHUB_AGENT_PORT", "9000")
        monkeypatch.setenv("AGENT_CONFIRM_MODE", "manual")
        
        # 重新加载配置
        settings = reload_settings()
        
        assert settings.github_agent_port == 9000
        assert settings.agent_confirm_mode == "manual"
    
    def test_ollama_config(self, mock_env_vars):
        """测试 Ollama 配置"""
        settings = get_settings()
        
        assert settings.ollama_host == "http://localhost:11434"
        assert settings.ollama_model == "test-model"
    
    def test_trigger_modes(self, mock_env_vars):
        """测试触发模式配置"""
        settings = get_settings()
        
        assert settings.github_agent_issue_trigger_mode in ["auto", "smart", "manual"]
        assert settings.github_agent_comment_trigger_mode in ["all", "smart", "manual"]
    
    def test_retry_config(self, mock_env_vars):
        """测试重试配置"""
        settings = get_settings()
        
        assert settings.max_retries >= 0
        assert settings.retry_delay > 0
        assert settings.retry_backoff >= 1.0


class TestLoggingConfig:
    """测试日志配置"""
    
    def test_setup_logging(self):
        """测试日志设置"""
        import logging
        from config.logging_config import setup_logging
        
        setup_logging(level="DEBUG")
        
        logger = logging.getLogger("test")
        assert logger.level == logging.DEBUG
    
    def test_contextual_logger(self):
        """测试上下文日志记录器"""
        from config.logging_config import get_logger
        
        logger = get_logger("test")
        
        # 测试普通日志
        logger.info("Test message")
        
        # 测试带上下文的日志
        with logger.context(request_id="123"):
            logger.info("Contextual message")
