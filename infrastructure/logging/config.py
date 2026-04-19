"""
日志配置管理

支持：
- YAML 配置文件加载
- 环境变量覆盖
- 默认配置
"""

import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .formatter import ConsoleFormatter, JSONFormatter, Colors


# 默认配置
DEFAULT_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            '()': 'infrastructure.logging.formatter.ConsoleFormatter',
            'show_location': False,
            'show_thread': False,
        },
        'json': {
            '()': 'infrastructure.logging.formatter.JSONFormatter',
            'ensure_ascii': False,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'console',
            'stream': 'ext://sys.stdout',
        },
    },
    'loggers': {
        # TermBot 核心日志
        'agent': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
        'llm': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
        'pty': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
        'tool': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
        'session': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
        'memory': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
        'skill': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
        'component': {'level': 'INFO', 'handlers': ['console'], 'propagate': False},
        
        # 屏蔽第三方库日志
        'jieba': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'httpx': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'httpcore': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'openai': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'urllib3': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'faiss': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'whoosh': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'werkzeug': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'engineio': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
        'socketio': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['console'],
    },
}


class LoggingConfig:
    """日志配置管理器"""
    
    _initialized = False
    
    @classmethod
    def setup(
        cls,
        level: Optional[str] = None,
        log_dir: Optional[str] = None,
        console_output: bool = True,
        file_output: bool = False,
        json_format: bool = False,
        disable_colors: bool = False,
    ) -> None:
        """
        初始化日志配置
        
        Args:
            level: 日志级别（DEBUG/INFO/WARNING/ERROR）
            log_dir: 日志文件目录
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            json_format: 是否使用 JSON 格式
            disable_colors: 是否禁用颜色
        """
        if cls._initialized:
            return
        
        # 禁用颜色
        if disable_colors or not sys.stdout.isatty():
            Colors.disable()
        
        # 从环境变量读取配置
        level = level or os.environ.get('LOG_LEVEL', 'INFO')
        log_dir = log_dir or os.environ.get('LOG_DIR', 'logs')
        console_output = console_output if 'LOG_TO_CONSOLE' not in os.environ else os.environ.get('LOG_TO_CONSOLE', 'true').lower() == 'true'
        file_output = file_output if 'LOG_TO_FILE' not in os.environ else os.environ.get('LOG_TO_FILE', 'false').lower() == 'true'
        json_format = json_format if 'LOG_JSON_FORMAT' not in os.environ else os.environ.get('LOG_JSON_FORMAT', 'false').lower() == 'true'
        
        # 构建配置
        config = cls._build_config(
            level=level,
            log_dir=log_dir,
            console_output=console_output,
            file_output=file_output,
            json_format=json_format,
        )
        
        # 应用配置
        logging.config.dictConfig(config)
        cls._initialized = True
    
    @classmethod
    def _build_config(
        cls,
        level: str,
        log_dir: str,
        console_output: bool,
        file_output: bool,
        json_format: bool,
    ) -> Dict[str, Any]:
        """构建日志配置字典"""
        config = DEFAULT_CONFIG.copy()
        
        # 更新日志级别
        config['root']['level'] = level
        for logger_config in config['loggers'].values():
            logger_config['level'] = level
        
        # 配置 handlers
        handlers = []
        
        if console_output:
            handlers.append('console')
            if json_format:
                config['handlers']['console']['formatter'] = 'json'
        
        if file_output:
            # 创建日志目录
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            
            # 添加文件 handler
            config['handlers']['file'] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'json',
                'filename': str(log_path / 'termbot.log'),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf-8',
            }
            handlers.append('file')
        
        # 更新所有 logger 的 handlers
        config['root']['handlers'] = handlers
        for logger_config in config['loggers'].values():
            logger_config['handlers'] = handlers
        
        return config
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取 Logger 实例
        
        Args:
            name: Logger 名称
            
        Returns:
            Logger 实例
        """
        if not cls._initialized:
            cls.setup()
        
        return logging.getLogger(name)


def init_logging(**kwargs) -> None:
    """
    初始化日志系统（便捷函数）
    
    Args:
        **kwargs: 传递给 LoggingConfig.setup 的参数
    """
    LoggingConfig.setup(**kwargs)


def _suppress_third_party_loggers():
    """强制屏蔽第三方库的日志输出"""
    suppress_list = [
        'jieba',
        'jieba.analyse',
        'httpx',
        'httpcore',
        'httpx._transports',
        'httpx._client',
        'openai',
        'urllib3',
        'urllib3.connectionpool',
        'faiss',
        'faiss.loader',
        'whoosh',
        'werkzeug',
        'engineio',
        'socketio',
        'flask',
        'flask.socketio',
    ]
    
    for name in suppress_list:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.disabled = True
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
    
    # 额外处理：faiss 使用不同的日志方式
    faiss_logger = logging.getLogger('faiss')
    faiss_logger.setLevel(logging.ERROR)
    faiss_logger.addHandler(logging.NullHandler())
    
    # 彻底禁用 httpx
    httpx_logger = logging.getLogger('httpx')
    httpx_logger.disabled = True
    httpx_logger.handlers = [logging.NullHandler()]
    httpx_logger.propagate = False
