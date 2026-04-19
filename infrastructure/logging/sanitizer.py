"""
敏感信息过滤器

自动过滤日志中的敏感信息,如：
- API Key
- Bearer Token
- Password
- 其他敏感数据
"""

import re
from typing import Any, Dict, List, Tuple, Optional

# 敏感信息正则模式
SENSITIVE_PATTERNS: List[Tuple[str, str]] = [
    # OpenAI API Key
    (r'sk-[a-zA-Z0-9]{48}', 'sk-***REDACTED***'),
    (r'sk-proj-[a-zA-Z0-9]{48}', 'sk-proj-***REDACTED***'),
    
    # Bearer Token
    (r'Bearer\s+[a-zA-Z0-9\-._~+/]+=', 'Bearer ***REDACTED***'),
    
    # Authorization Header
    (r'Authorization:\s*[Bb]earer\s+[^\s]+', 'Authorization: Bearer ***REDACTED***'),
    
    # API Key in URL or params
    (r'api_key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9\-_]{20,}', 'api_key=***REDACTED***'),
    (r'apikey["\']?\s*[:=]\s*["\']?[a-zA-Z0-9\-_]{20,}', 'apikey=***REDACTED***'),
    
    # Password
    (r'password["\']?\s*[:=]\s*["\']?[^\s"\']+', 'password=***REDACTED***'),
    (r'passwd["\']?\s*[:=]\s*["\']?[^\s"\']+', 'passwd=***REDACTED***'),
    
    # Secret/Token
    (r'secret["\']?\s*[:=]\s*["\']?[^\s"\']+', 'secret=***REDACTED***'),
    (r'token["\']?\s*[:=]\s*["\']?[a-zA-Z0-9\-._~+/]{20,}', 'token=***REDACTED***'),
    
    # AWS Access Key
    (r'AKIA[0-9A-Z]{16}', 'AKIA***REDACTED***'),
    
    # Private Key markers
    (r'-----BEGIN\s+PRIVATE\s+KEY-----[\s\S]*?-----END\s+PRIVATE\s+KEY-----', 
     '-----BEGIN PRIVATE KEY-----***REDACTED***-----END PRIVATE KEY-----'),
]

# 敏感字段名（用于字典过滤）
SENSITIVE_KEYS = {
    'password', 'passwd', 'pwd',
    'secret', 'secret_key', 'secretkey',
    'token', 'access_token', 'accesstoken', 'refresh_token',
    'api_key', 'apikey', 'api-key',
    'private_key', 'privatekey', 'private-key',
    'authorization', 'auth',
    'credential', 'credentials',
}


def sanitize_string(text: str) -> str:
    """
    过滤字符串中的敏感信息
    
    Args:
        text: 原始字符串
        
    Returns:
        过滤后的字符串
    """
    if not isinstance(text, str):
        return text
    
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def sanitize_dict(data: Dict[str, Any], depth: int = 0, max_depth: int = 10) -> Dict[str, Any]:
    """
    递归过滤字典中的敏感信息
    
    Args:
        data: 原始字典
        depth: 当前递归深度
        max_depth: 最大递归深度
        
    Returns:
        过滤后的字典
    """
    if depth > max_depth:
        return data
    
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        key_lower = key.lower() if isinstance(key, str) else str(key).lower()
        
        # 检查键名是否敏感
        if key_lower in SENSITIVE_KEYS:
            result[key] = '***REDACTED***'
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, depth + 1, max_depth)
        elif isinstance(value, str):
            result[key] = sanitize_string(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, depth + 1, max_depth) if isinstance(item, dict)
                else sanitize_string(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


def sanitize(data: Any) -> Any:
    """
    通用敏感信息过滤入口
    
    Args:
        data: 任意数据（字符串、字典、列表等）
        
    Returns:
        过滤后的数据
    """
    if isinstance(data, str):
        return sanitize_string(data)
    elif isinstance(data, dict):
        return sanitize_dict(data)
    elif isinstance(data, list):
        return [
            sanitize_dict(item) if isinstance(item, dict)
            else sanitize_string(item) if isinstance(item, str)
            else item
            for item in data
        ]
    else:
        return data
