#!/usr/bin/env python3
"""
应用配置

使用 Pydantic 进行配置验证和管理
"""

import os
from typing import Optional, List
from functools import lru_cache

# 尝试导入 pydantic，如果没有则使用简单的 dataclass
try:
    from pydantic import Field, validator
    from pydantic_settings import BaseSettings
    HAS_PYDANTIC = True
except ImportError:
    from dataclasses import dataclass, field
    HAS_PYDANTIC = False
    
    # 简单的 BaseSettings 替代
    class BaseSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            self._load_from_env()
        
        def _load_from_env(self):
            """从环境变量加载配置"""
            for attr_name in dir(self):
                if attr_name.startswith('_'):
                    continue
                env_name = attr_name.upper()
                env_value = os.environ.get(env_name)
                if env_value is not None:
                    current_value = getattr(self, attr_name, None)
                    if isinstance(current_value, bool):
                        setattr(self, attr_name, env_value.lower() in ('true', '1', 'yes', 'on'))
                    elif isinstance(current_value, int):
                        setattr(self, attr_name, int(env_value))
                    elif isinstance(current_value, float):
                        setattr(self, attr_name, float(env_value))
                    else:
                        setattr(self, attr_name, env_value)


if HAS_PYDANTIC:
    class Settings(BaseSettings):
        """应用配置类"""
        
        # GitHub App 配置
        github_app_id: str = Field(default="", description="GitHub App ID")
        github_private_key_path: str = Field(default="", description="GitHub App 私钥路径")
        github_webhook_secret: str = Field(default="", description="GitHub Webhook Secret")
        
        # Webhook 服务器配置
        github_agent_host: str = Field(default="0.0.0.0", description="Webhook 服务器监听地址")
        github_agent_port: int = Field(default=8080, description="Webhook 服务器端口")
        
        # 触发模式配置
        github_agent_issue_trigger_mode: str = Field(default="smart", description="Issue 触发模式: auto, smart, manual")
        github_agent_comment_trigger_mode: str = Field(default="smart", description="评论触发模式: all, smart, manual")
        
        # 确认模式配置
        agent_confirm_mode: str = Field(default="auto", description="确认模式: auto, manual")
        agent_auto_confirm_threshold: float = Field(default=0.8, description="自动确认置信度阈值")
        
        # OpenClaw 配置 (云端意图识别)
        openclaw_url: str = Field(default="http://localhost:3000", description="OpenClaw 服务地址")
        openclaw_model: str = Field(default="kimi-k2.5", description="OpenClaw 使用模型")
        openclaw_timeout: int = Field(default=60, description="OpenClaw 请求超时(秒)")
        
        # Ollama 配置 (本地代码生成)
        ollama_host: str = Field(default="http://localhost:11434", description="Ollama 服务地址")
        ollama_model: str = Field(default="qwen3-coder:30b", description="Ollama 使用模型")
        ollama_timeout: int = Field(default=300, description="Ollama 请求超时(秒)")
        
        # 知识库服务配置
        kb_service_url: str = Field(default="http://localhost:8000", description="知识库服务地址")
        kb_timeout: int = Field(default=30, description="知识库请求超时(秒)")
        
        # 工作目录配置
        github_agent_workdir: str = Field(default="/tmp/github-agent-v2", description="工作目录")
        github_agent_statedir: str = Field(default="./state", description="状态存储目录")
        
        # 日志配置
        log_level: str = Field(default="INFO", description="日志级别")
        log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式")
        
        # 安全配置
        max_file_size: int = Field(default=1024*1024, description="最大文件大小(字节)")
        max_files_per_pr: int = Field(default=10, description="每个 PR 最大文件数")
        allowed_file_extensions: List[str] = Field(
            default=[".py", ".js", ".ts", ".json", ".md", ".yml", ".yaml", ".txt"],
            description="允许修改的文件扩展名"
        )
        
        # 重试配置
        max_retries: int = Field(default=3, description="最大重试次数")
        retry_delay: float = Field(default=1.0, description="重试间隔(秒)")
        retry_backoff: float = Field(default=2.0, description="重试退避系数")
        
        class Config:
            env_prefix = ""  # 环境变量不需要前缀
            case_sensitive = False
        
        @validator('github_agent_issue_trigger_mode', 'github_agent_comment_trigger_mode')
        def validate_trigger_mode(cls, v):
            allowed = ['auto', 'smart', 'manual', 'all']
            if v not in allowed:
                raise ValueError(f"触发模式必须是以下之一: {allowed}")
            return v
        
        @validator('agent_confirm_mode')
        def validate_confirm_mode(cls, v):
            allowed = ['auto', 'manual']
            if v not in allowed:
                raise ValueError(f"确认模式必须是以下之一: {allowed}")
            return v
        
        @validator('agent_auto_confirm_threshold')
        def validate_threshold(cls, v):
            if not 0 <= v <= 1:
                raise ValueError("置信度阈值必须在 0-1 之间")
            return v

else:
    # 无 Pydantic 时的简单配置类
    @dataclass
    class Settings(BaseSettings):
        """应用配置类 (简化版)"""
        
        # GitHub App 配置
        github_app_id: str = ""
        github_private_key_path: str = ""
        github_webhook_secret: str = ""
        
        # Webhook 服务器配置
        github_agent_host: str = "0.0.0.0"
        github_agent_port: int = 8080
        
        # 触发模式配置
        github_agent_issue_trigger_mode: str = "smart"
        github_agent_comment_trigger_mode: str = "smart"
        
        # 确认模式配置
        agent_confirm_mode: str = "auto"
        agent_auto_confirm_threshold: float = 0.8
        
        # OpenClaw 配置
        openclaw_url: str = "http://localhost:3000"
        openclaw_model: str = "kimi-k2.5"
        openclaw_timeout: int = 60
        
        # Ollama 配置
        ollama_host: str = "http://localhost:11434"
        ollama_model: str = "qwen3-coder:30b"
        ollama_timeout: int = 300
        
        # 知识库服务配置
        kb_service_url: str = "http://localhost:8000"
        kb_timeout: int = 30
        
        # 工作目录配置
        github_agent_workdir: str = "/tmp/github-agent-v2"
        github_agent_statedir: str = "./state"
        
        # 日志配置
        log_level: str = "INFO"
        log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # 安全配置
        max_file_size: int = 1024 * 1024
        max_files_per_pr: int = 10
        allowed_file_extensions: list = field(default_factory=lambda: [
            ".py", ".js", ".ts", ".json", ".md", ".yml", ".yaml", ".txt"
        ])
        
        # 重试配置
        max_retries: int = 3
        retry_delay: float = 1.0
        retry_backoff: float = 2.0


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例
    
    使用 LRU 缓存确保配置只被创建一次
    
    Returns:
        Settings 实例
    """
    return Settings()


def reload_settings() -> Settings:
    """
    重新加载配置
    
    清除缓存并重新创建配置实例
    
    Returns:
        新的 Settings 实例
    """
    get_settings.cache_clear()
    return get_settings()


def print_settings(settings: Settings = None) -> None:
    """
    打印当前配置（用于调试）
    
    Args:
        settings: 配置实例，默认使用全局配置
    """
    if settings is None:
        settings = get_settings()
    
    print("=" * 50)
    print("GitHub Agent V2 配置")
    print("=" * 50)
    
    groups = {
        "GitHub App": ["github_app_id", "github_private_key_path"],
        "Webhook 服务器": ["github_agent_host", "github_agent_port"],
        "触发模式": ["github_agent_issue_trigger_mode", "github_agent_comment_trigger_mode"],
        "确认模式": ["agent_confirm_mode", "agent_auto_confirm_threshold"],
        "OpenClaw": ["openclaw_url", "openclaw_model", "openclaw_timeout"],
        "Ollama": ["ollama_host", "ollama_model", "ollama_timeout"],
        "知识库": ["kb_service_url", "kb_timeout"],
        "工作目录": ["github_agent_workdir", "github_agent_statedir"],
        "日志": ["log_level"],
    }
    
    for group_name, attrs in groups.items():
        print(f"\n【{group_name}】")
        for attr in attrs:
            value = getattr(settings, attr, None)
            # 隐藏敏感信息
            if 'secret' in attr or 'key' in attr:
                if value and len(str(value)) > 10:
                    value = str(value)[:10] + "..."
            print(f"  {attr}: {value}")
    
    print("\n" + "=" * 50)


# 向后兼容的别名
Config = Settings
get_config = get_settings
