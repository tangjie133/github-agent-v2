#!/usr/bin/env python3
"""
日志配置

提供统一的日志配置和结构化日志支持
"""

import sys
import logging
from typing import Optional


def setup_logging(
    level: str = "INFO",
    format_str: str = None,
    log_file: str = None,
    use_json: bool = False
):
    """
    设置日志配置
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_str: 日志格式字符串
        log_file: 日志文件路径，None 表示只输出到控制台
        use_json: 是否使用 JSON 格式（便于日志收集系统解析）
    """
    # 默认格式
    if format_str is None:
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    root_logger.handlers = []
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    if use_json:
        try:
            import json
            
            class JsonFormatter(logging.Formatter):
                def format(self, record):
                    log_data = {
                        "timestamp": self.formatTime(record),
                        "level": record.levelname,
                        "logger": record.name,
                        "message": record.getMessage(),
                        "module": record.module,
                        "function": record.funcName,
                        "line": record.lineno,
                    }
                    if record.exc_info:
                        log_data["exception"] = self.formatException(record.exc_info)
                    return json.dumps(log_data, ensure_ascii=False)
            
            console_handler.setFormatter(JsonFormatter())
        except ImportError:
            console_handler.setFormatter(logging.Formatter(format_str))
    else:
        console_handler.setFormatter(logging.Formatter(format_str))
    
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(logging.Formatter(format_str))
        root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    
    logging.info(f"日志配置完成: level={level}, json={use_json}")


class ContextualLogger:
    """
    带上下文的日志记录器
    
    自动添加请求上下文信息到日志中
    
    Example:
        logger = ContextualLogger(logging.getLogger(__name__))
        with logger.context(request_id="123", user="test"):
            logger.info("处理请求")  # 输出会包含 request_id 和 user
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._context = {}
    
    def context(self, **kwargs):
        """设置上下文（上下文管理器）"""
        return _ContextManager(self, kwargs)
    
    def _format_message(self, msg: str) -> str:
        """添加上下文信息到消息"""
        if self._context:
            context_str = " ".join([f"[{k}={v}]" for k, v in self._context.items()])
            return f"{context_str} {msg}"
        return msg
    
    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(self._format_message(msg), *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self.logger.info(self._format_message(msg), *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(self._format_message(msg), *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self.logger.error(self._format_message(msg), *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        self.logger.exception(self._format_message(msg), *args, **kwargs)


class _ContextManager:
    """上下文管理器实现"""
    
    def __init__(self, contextual_logger: ContextualLogger, context: dict):
        self.logger = contextual_logger
        self.context = context
        self.previous_context = {}
    
    def __enter__(self):
        self.previous_context = self.logger._context.copy()
        self.logger._context.update(self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger._context = self.previous_context


def get_logger(name: str) -> ContextualLogger:
    """
    获取带上下文的日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        ContextualLogger 实例
    """
    return ContextualLogger(logging.getLogger(name))
