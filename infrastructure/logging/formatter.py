"""
日志格式化器

提供多种日志格式：
- ConsoleFormatter: 控制台彩色输出
- JSONFormatter: 结构化 JSON 输出
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional


# ANSI 颜色代码
class Colors:
    """终端颜色常量"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # 前景色
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # 亮色
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    
    @classmethod
    def disable(cls):
        """禁用颜色（非 TTY 环境）"""
        cls.RESET = ''
        cls.BOLD = ''
        cls.DIM = ''
        cls.RED = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.BLUE = ''
        cls.MAGENTA = ''
        cls.CYAN = ''
        cls.WHITE = ''
        cls.BRIGHT_RED = ''
        cls.BRIGHT_GREEN = ''
        cls.BRIGHT_YELLOW = ''
        cls.BRIGHT_BLUE = ''
        cls.BRIGHT_MAGENTA = ''
        cls.BRIGHT_CYAN = ''


# 日志级别颜色映射
LEVEL_COLORS = {
    'DEBUG': Colors.DIM,
    'INFO': Colors.GREEN,
    'WARNING': Colors.YELLOW,
    'ERROR': Colors.RED,
    'CRITICAL': Colors.BRIGHT_RED,
}


class JSONFormatter(logging.Formatter):
    """
    JSON 格式化器
    
    输出结构化 JSON 日志，便于日志分析系统处理
    """
    
    def __init__(self, ensure_ascii: bool = False, indent: Optional[int] = None):
        super().__init__()
        self.ensure_ascii = ensure_ascii
        self.indent = indent
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化为 JSON"""
        # 基础字段
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # 位置信息
        if record.pathname:
            log_data['location'] = {
                'file': record.pathname,
                'line': record.lineno,
                'function': record.funcName,
            }
        
        # 异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # 额外字段（从 record.__dict__ 中提取）
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'message', 'asctime'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_data['extra'] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=self.ensure_ascii, indent=self.indent, default=str)


class ConsoleFormatter(logging.Formatter):
    """
    控制台格式化器
    
    输出彩色、可读性强的日志格式
    """
    
    # 时间格式
    TIME_FORMAT = '%H:%M:%S'
    
    def __init__(self, show_location: bool = False, show_thread: bool = False):
        super().__init__()
        self.show_location = show_location
        self.show_thread = show_thread
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化为控制台输出"""
        # 时间
        timestamp = datetime.now().strftime(self.TIME_FORMAT)
        
        # 级别（带颜色）
        level_color = LEVEL_COLORS.get(record.levelname, Colors.WHITE)
        level = f"{level_color}{Colors.BOLD}{record.levelname:7}{Colors.RESET}"
        
        # Logger 名称
        logger_name = self._shorten_name(record.name)
        
        # 上下文信息
        context_str = self._format_context(record)
        
        # 消息
        message = record.getMessage()
        
        # 组装基础行
        parts = [f"{Colors.DIM}[{timestamp}]{Colors.RESET}", level, f"{Colors.CYAN}{logger_name}{Colors.RESET}"]
        if context_str:
            parts.append(f"{Colors.MAGENTA}{context_str}{Colors.RESET}")
        parts.append(message)
        
        result = ' '.join(parts)
        
        # 事件详情（缩进）
        event_data = getattr(record, 'event_data', None)
        if event_data:
            result += self._format_event_data(event_data)
        
        # 位置信息
        if self.show_location:
            result += f"\n  {Colors.DIM}↳ {record.filename}:{record.lineno}{Colors.RESET}"
        
        # 异常信息
        if record.exc_info:
            result += f"\n{Colors.RED}{self.formatException(record.exc_info)}{Colors.RESET}"
        
        return result
    
    def _shorten_name(self, name: str, max_len: int = 25) -> str:
        """缩短 logger 名称"""
        if len(name) <= max_len:
            return name
        
        # 保留最后部分
        parts = name.split('.')
        if len(parts) > 1:
            shortened = '.'.join(p[0] for p in parts[:-1]) + '.' + parts[-1]
            if len(shortened) <= max_len:
                return shortened
        
        return '...' + name[-(max_len - 3):]
    
    def _format_context(self, record: logging.LogRecord) -> str:
        """格式化上下文信息"""
        context_parts = []
        
        session_id = getattr(record, 'session_id', None)
        if session_id:
            context_parts.append(f"session:{session_id[:8]}")
        
        agent_id = getattr(record, 'agent_id', None)
        if agent_id:
            context_parts.append(f"agent:{agent_id[:8]}")
        
        return f"[{', '.join(context_parts)}]" if context_parts else ''
    
    def _format_event_data(self, data: Dict[str, Any], indent: str = '  ') -> str:
        """格式化事件数据"""
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                value_str = json.dumps(value, ensure_ascii=False, default=str)
                if len(value_str) > 400:
                    value_str = value_str[:400] + '...'
            elif isinstance(value, str) and len(value) > 400:
                value_str = value[:400] + '...'
            else:
                value_str = str(value)
            
            lines.append(f"\n{indent}{Colors.DIM}├─ {key}:{Colors.RESET} {value_str}")
        
        return ''.join(lines)