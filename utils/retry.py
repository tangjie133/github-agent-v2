#!/usr/bin/env python3
"""
重试机制

提供可配置的重试装饰器和函数
"""

import time
import logging
import functools
from typing import Type, Tuple, Optional, Callable, Any

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """可重试的错误基类"""
    pass


class MaxRetriesExceeded(Exception):
    """超过最大重试次数"""
    pass


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    on_success: Optional[Callable[[], None]] = None,
    on_failure: Optional[Callable[[Exception], None]] = None
):
    """
    重试装饰器
    
    为函数添加自动重试功能，支持指数退避
    
    Args:
        max_retries: 最大重试次数
        delay: 初始重试延迟（秒）
        backoff: 退避系数，每次重试后延迟乘以该系数
        exceptions: 需要重试的异常类型元组
        on_retry: 每次重试时的回调函数，参数为 (异常, 重试次数)
        on_success: 成功时的回调函数
        on_failure: 最终失败时的回调函数
        
    Returns:
        装饰器函数
        
    Example:
        @retry(max_retries=3, delay=1.0, exceptions=(ConnectionError,))
        def fetch_data():
            return requests.get(url)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if on_success:
                        on_success()
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"函数 {func.__name__} 第 {attempt + 1} 次执行失败: {e}, "
                            f"{current_delay:.1f}秒后重试..."
                        )
                        
                        if on_retry:
                            on_retry(e, attempt + 1)
                        
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"函数 {func.__name__} 在 {max_retries} 次重试后仍然失败"
                        )
            
            # 所有重试都失败了
            if on_failure:
                on_failure(last_exception)
            
            raise MaxRetriesExceeded(
                f"函数 {func.__name__} 在 {max_retries} 次重试后失败: {last_exception}"
            ) from last_exception
        
        return wrapper
    return decorator


def retry_with_config(config=None):
    """
    使用配置中的重试参数的装饰器
    
    Args:
        config: 配置对象，默认使用全局配置
        
    Returns:
        配置化的 retry 装饰器
        
    Example:
        @retry_with_config()
        def api_call():
            return requests.get(url)
    """
    if config is None:
        try:
            from config import get_settings
            config = get_settings()
        except ImportError:
            # 使用默认配置
            return retry()
    
    return retry(
        max_retries=getattr(config, 'max_retries', 3),
        delay=getattr(config, 'retry_delay', 1.0),
        backoff=getattr(config, 'retry_backoff', 2.0)
    )


class RetryContext:
    """
    重试上下文管理器
    
    用于需要更细粒度控制重试逻辑的场景
    
    Example:
        with RetryContext(max_retries=3) as retry_ctx:
            for attempt in retry_ctx.attempts():
                try:
                    result = risky_operation()
                    retry_ctx.success()
                    break
                except ConnectionError:
                    retry_ctx.retry()
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
        self.exceptions = exceptions
        
        self.attempt_count = 0
        self.current_delay = delay
        self.succeeded = False
        self.last_exception = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.succeeded and self.attempt_count > 0:
            logger.error(f"重试上下文在 {self.attempt_count} 次尝试后失败")
        return False
    
    def attempts(self):
        """生成器，产生尝试次数"""
        for i in range(self.max_retries + 1):
            self.attempt_count = i + 1
            yield i
            
            if self.succeeded:
                break
            
            if i < self.max_retries:
                logger.warning(f"等待 {self.current_delay:.1f} 秒后重试...")
                time.sleep(self.current_delay)
                self.current_delay *= self.backoff
    
    def success(self):
        """标记成功"""
        self.succeeded = True
        logger.debug(f"操作在第 {self.attempt_count} 次尝试成功")
    
    def retry(self, exception: Optional[Exception] = None):
        """标记需要重试"""
        if exception:
            self.last_exception = exception
            logger.warning(f"第 {self.attempt_count} 次尝试失败: {exception}")
    
    def fail(self, message: str = "操作失败"):
        """标记失败，不再重试"""
        raise MaxRetriesExceeded(f"{message}，已尝试 {self.attempt_count} 次")


# 预定义的常用重试配置

retry_on_network_error = retry(
    max_retries=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(ConnectionError, TimeoutError, IOError)
)

retry_on_api_error = retry(
    max_retries=5,
    delay=2.0,
    backoff=1.5,
    exceptions=(ConnectionError, TimeoutError)
)

retry_on_git_error = retry(
    max_retries=2,
    delay=0.5,
    backoff=2.0,
    exceptions=(RuntimeError,)
)


def with_fallback(primary_func: Callable, fallback_func: Callable):
    """
    带降级方案的执行
    
    先尝试主函数，失败时执行降级函数
    
    Args:
        primary_func: 主函数
        fallback_func: 降级函数
        
    Returns:
        包装后的函数
        
    Example:
        @with_fallback(primary_api_call, cached_api_call)
        def get_data():
            pass
    """
    @functools.wraps(primary_func)
    def wrapper(*args, **kwargs):
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"主函数失败，使用降级方案: {e}")
            return fallback_func(*args, **kwargs)
    return wrapper
