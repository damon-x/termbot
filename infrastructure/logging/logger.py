"""
结构化日志记录器

提供：
- 标准日志级别方法
- 结构化事件记录
- 性能计时器
- 自动上下文注入
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from .context import logger_context
from .sanitizer import sanitize
from .config import LoggingConfig


class StructuredLogger:
    """
    结构化日志记录器
    
    封装 Python logging，提供：
    1. 自动上下文注入（session_id, agent_id）
    2. 结构化事件记录
    3. 敏感信息自动过滤
    4. 性能计时
    """
    
    def __init__(self, name: str):
        """
        初始化 Logger
        
        Args:
            name: Logger 名称（通常使用模块名）
        """
        self._name = name
        self._logger: Optional[logging.Logger] = None
    
    @property
    def logger(self) -> logging.Logger:
        """延迟获取 Logger 实例"""
        if self._logger is None:
            self._logger = LoggingConfig.get_logger(self._name)
        return self._logger
    
    def _get_context(self) -> Dict[str, Any]:
        """获取当前上下文"""
        return logger_context.get_context()
    
    def _log(self, level: int, msg: str, *args, **kwargs) -> None:
        """
        内部日志方法，自动注入上下文
        
        Args:
            level: 日志级别
            msg: 消息
            *args: 格式化参数
            **kwargs: 额外字段
        """
        # 获取上下文
        context = self._get_context()
        
        # 合并上下文到 extra
        extra = kwargs.pop('extra', {})
        extra.update(context)
        
        # 合并其他 kwargs 到 extra
        for key in list(kwargs.keys()):
            if key not in ('exc_info', 'stack_info', 'stacklevel', 'extra'):
                extra[key] = kwargs.pop(key)
        
        kwargs['extra'] = extra
        
        try:
            self.logger.log(level, msg, *args, **kwargs)
        except Exception:
            # 日志失败不应影响业务，静默忽略
            pass
    
    # ============================================
    # 标准日志级别方法
    # ============================================
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """DEBUG 级别日志"""
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """INFO 级别日志"""
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """WARNING 级别日志"""
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, exc_info: bool = False, **kwargs) -> None:
        """
        ERROR 级别日志
        
        Args:
            msg: 消息
            exc_info: 是否包含异常信息
            **kwargs: 额外字段
        """
        kwargs['exc_info'] = exc_info
        self._log(logging.ERROR, msg, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """CRITICAL 级别日志"""
        self._log(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs) -> None:
        """记录异常（自动包含异常堆栈）"""
        kwargs['exc_info'] = True
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    # ============================================
    # 结构化事件记录
    # ============================================
    
    def log_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
        sanitize_data: bool = True,
    ) -> None:
        """
        记录结构化事件
        
        Args:
            event_type: 事件类型（使用 EventType 常量）
            data: 事件数据
            level: 日志级别
            sanitize_data: 是否过滤敏感信息
        """
        # 过滤敏感信息
        if sanitize_data and data:
            data = sanitize(data)
        
        # 构建事件数据
        event_data = {
            'event_type': event_type,
            **(data or {}),
        }
        
        # 获取日志级别
        level_int = getattr(logging, level.upper(), logging.INFO)
        
        # 记录日志
        self._log(level_int, f"[{event_type}]", event_data=event_data, **(data or {}))
    
    # ============================================
    # 性能计时
    # ============================================
    
    @contextmanager
    def timer(self, operation: str, **metadata):
        """
        性能计时上下文管理器
        
        Args:
            operation: 操作名称
            **metadata: 额外元数据
            
        Usage:
            with logger.timer("api_call", endpoint="/chat"):
                result = api.chat()
            # 自动记录耗时
        """
        start_time = time.perf_counter()
        error = None
        
        try:
            yield
        except Exception as e:
            error = str(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            data = {
                'operation': operation,
                'duration_ms': round(duration_ms, 2),
                **metadata,
            }
            
            if error:
                data['error'] = error
            
            self.log_event(
                event_type="performance_metric",
                data=data,
                level="DEBUG",
            )
    
    # ============================================
    # 便捷方法
    # ============================================
    
    def with_context(self, **kwargs) -> "StructuredLogger":
        """
        返回带有额外上下文的 Logger
        
        Args:
            **kwargs: 上下文键值对
            
        Note:
            这只是语义上的便捷，实际上下文需要通过 logger_context 设置
        """
        return self
    
    def bind(self, **kwargs) -> "BoundLogger":
        """
        绑定额外字段到 Logger
        
        Args:
            **kwargs: 要绑定的字段
            
        Returns:
            BoundLogger 实例
        """
        return BoundLogger(self, kwargs)


class BoundLogger:
    """
    绑定字段的 Logger
    
    用于临时添加额外字段到所有日志
    """
    
    def __init__(self, logger: StructuredLogger, extra: Dict[str, Any]):
        self._logger = logger
        self._extra = extra
    
    def _log_with_extra(self, level: int, msg: str, *args, **kwargs) -> None:
        """带额外字段的日志"""
        extra = kwargs.pop('extra', {})
        extra.update(self._extra)
        kwargs['extra'] = extra
        self._logger._log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log_with_extra(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        self._log_with_extra(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log_with_extra(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        self._log_with_extra(logging.ERROR, msg, *args, **kwargs)


# ============================================
# 全局 Logger 缓存
# ============================================

_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str) -> StructuredLogger:
    """
    获取 StructuredLogger 实例
    
    Args:
        name: Logger 名称（通常使用 __name__）
        
    Returns:
        StructuredLogger 实例
        
    Usage:
        logger = get_logger(__name__)
        logger.info("Hello")
    """
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name)
    return _loggers[name]
