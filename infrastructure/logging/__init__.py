"""
TermBot 结构化日志系统

提供统一的日志记录接口，支持：
- 结构化事件记录
- 会话上下文管理
- 敏感信息过滤
- 多格式输出（控制台/JSON）
"""

import logging
import os
import sys

# 设置环境变量避免 faiss 检查 CPU
os.environ.setdefault('FAISS_OPT_LEVEL', 'AVX2')

# ========== 关键：在任何其他模块导入前，立即禁用所有第三方库日志 ==========

# 禁用 httpx 和 httpcore - 必须在导入 httpx 之前
for _httpx_name in ['httpx', 'httpx.client', 'httpx._client', 'httpx._transports', 'httpx._transports.default', 'httpx._transports.http', 'httpx._transports.http2', 'httpx._exceptions', 'httpx._urls']:
    _logger = logging.getLogger(_httpx_name)
    _logger.handlers = [logging.NullHandler()]
    _logger.propagate = False
    _logger.setLevel(logging.CRITICAL)
    _logger.disabled = True

# 禁用 httpcore (httpx 底层)
for _httpcore_name in ['httpcore', 'httpcore.connection', 'httpcore.http11', 'httpcore.http2']:
    _logger = logging.getLogger(_httpcore_name)
    _logger.handlers = [logging.NullHandler()]
    _logger.propagate = False
    _logger.setLevel(logging.CRITICAL)
    _logger.disabled = True

# 禁用其他第三方库
_suppress_list = [
    'jieba', 'jieba.analyse',
    'httpcore', 'httpx._transports.default', 'httpx._client', 'httpx._transports',
    'openai', 'openai._base_client',
    'urllib3', 'urllib3.connectionpool', 'urllib3.util', 'urllib3.response',
    'faiss', 'faiss.loader', 'faiss.gpu', 'faiss.swigfaiss',
    'whoosh', 'whoosh.index', 'whoosh.qparser', 'whoosh.search', 'whoosh.fields',
    'werkzeug', 'werkzeug.serving', 'werkzeug._internal', 'werkzeug.debug',
    'engineio', 'engineio.server', 'engineio.client', 'engineio.async_drivers',
    'socketio', 'socketio.server', 'socketio.client', 'socketio.base_manager', 'socketio.namespace',
    'flask', 'flask.app',
    'sqlalchemy', 'sqlalchemy.engine',
]
for _name in _suppress_list:
    _logger = logging.getLogger(_name)
    _logger.setLevel(logging.CRITICAL)
    _logger.disabled = True
    _logger.addHandler(logging.NullHandler())
    _logger.propagate = False

# 特别处理：禁用 werkzeug 的 access log
try:
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.log_request = lambda self, *args, **kwargs: None
except:
    pass

# ========== 现在安全地导入我们的模块 ==========

from .logger import get_logger, StructuredLogger
from .context import ContextManager, logger_context
from .events import EventType
from .sanitizer import sanitize, sanitize_dict
from .config import init_logging, LoggingConfig

__all__ = [
    # 核心接口
    'get_logger',
    'StructuredLogger',
    
    # 上下文管理
    'ContextManager',
    'logger_context',
    
    # 事件类型
    'EventType',
    
    # 敏感信息过滤
    'sanitize',
    'sanitize_dict',
    
    # 配置
    'init_logging',
    'LoggingConfig',
]
