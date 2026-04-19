"""
会话上下文管理

提供线程安全的日志上下文管理，支持：
- session_id: 会话标识
- agent_id: Agent 标识
- 其他自定义上下文
"""

import threading
from typing import Optional, Dict, Any
from contextlib import contextmanager


class ContextManager:
    """
    线程安全的日志上下文管理器
    
    使用 threading.local 确保多线程环境下上下文隔离
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._local = threading.local()
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "ContextManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_session(self, session_id: str, **kwargs) -> None:
        """
        设置会话上下文
        
        Args:
            session_id: 会话ID
            **kwargs: 其他上下文信息（mode, user_ip 等）
        """
        if not hasattr(self._local, 'context'):
            self._local.context = {}
        
        self._local.context['session_id'] = session_id
        self._local.context.update(kwargs)
    
    def set_agent(self, agent_id: str, **kwargs) -> None:
        """
        设置 Agent 上下文
        
        Args:
            agent_id: Agent ID
            **kwargs: 其他上下文信息（role 等）
        """
        if not hasattr(self._local, 'context'):
            self._local.context = {}
        
        self._local.context['agent_id'] = agent_id
        self._local.context.update(kwargs)
    
    def set(self, **kwargs) -> None:
        """
        设置任意上下文
        
        Args:
            **kwargs: 上下文键值对
        """
        if not hasattr(self._local, 'context'):
            self._local.context = {}
        self._local.context.update(kwargs)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取单个上下文值
        
        Args:
            key: 键名
            default: 默认值
            
        Returns:
            上下文值
        """
        if not hasattr(self._local, 'context'):
            return default
        return self._local.context.get(key, default)
    
    def get_context(self) -> Dict[str, Any]:
        """
        获取完整上下文（副本）
        
        Returns:
            上下文字典副本
        """
        if not hasattr(self._local, 'context'):
            return {}
        return dict(self._local.context)
    
    def clear(self) -> None:
        """清除当前线程的上下文"""
        if hasattr(self._local, 'context'):
            self._local.context = {}
    
    @contextmanager
    def scope(self, **kwargs):
        """
        临时上下文作用域
        
        Args:
            **kwargs: 临时上下文
            
        Usage:
            with logger_context.scope(request_id='abc123'):
                logger.info("Processing")  # 包含 request_id
            # request_id 自动清除
        """
        old_context = self.get_context()
        self.set(**kwargs)
        try:
            yield
        finally:
            self.clear()
            if old_context:
                self._local.context = old_context


# 全局便捷实例
logger_context = ContextManager.get_instance()
