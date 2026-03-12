#!/usr/bin/env python3
"""
错误定义

定义项目中使用的自定义异常类
"""


class AgentError(Exception):
    """GitHub Agent 基础错误"""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code or "AGENT_ERROR"
        self.details = details or {}
    
    def __str__(self):
        if self.details:
            return f"[{self.code}] {self.message} - Details: {self.details}"
        return f"[{self.code}] {self.message}"


class GitHubAPIError(AgentError):
    """GitHub API 错误"""
    
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(
            message=message,
            code="GITHUB_API_ERROR",
            details={"status_code": status_code, "response": response}
        )
        self.status_code = status_code
        self.response = response


class AuthenticationError(AgentError):
    """认证错误"""
    
    def __init__(self, message: str = "认证失败"):
        super().__init__(message, code="AUTH_ERROR")


class ConfigurationError(AgentError):
    """配置错误"""
    
    def __init__(self, message: str, config_key: str = None):
        super().__init__(message, code="CONFIG_ERROR")
        self.config_key = config_key


class CodeExecutionError(AgentError):
    """代码执行错误"""
    
    def __init__(self, message: str, file_path: str = None, error_output: str = None):
        super().__init__(
            message=message,
            code="CODE_EXEC_ERROR",
            details={"file_path": file_path, "error_output": error_output}
        )
        self.file_path = file_path
        self.error_output = error_output


class ValidationError(AgentError):
    """验证错误"""
    
    def __init__(self, message: str, validation_errors: list = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"errors": validation_errors}
        )
        self.validation_errors = validation_errors or []


class KnowledgeBaseError(AgentError):
    """知识库错误"""
    
    def __init__(self, message: str, query: str = None):
        super().__init__(message, code="KB_ERROR", details={"query": query})
        self.query = query


class IntentClassificationError(AgentError):
    """意图识别错误"""
    
    def __init__(self, message: str, raw_response: str = None):
        super().__init__(message, code="INTENT_ERROR", details={"raw": raw_response})
        self.raw_response = raw_response


class WebhookError(AgentError):
    """Webhook 处理错误"""
    
    def __init__(self, message: str, event_type: str = None):
        super().__init__(message, code="WEBHOOK_ERROR", details={"event_type": event_type})
        self.event_type = event_type


class ServiceUnavailableError(AgentError):
    """服务不可用错误"""
    
    def __init__(self, message: str, service_name: str = None):
        super().__init__(message, code="SERVICE_UNAVAILABLE")
        self.service_name = service_name
