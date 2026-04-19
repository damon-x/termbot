# 阶段一：基础重构（代码规范与模块拆分）

## 目标

代码规范化，初步模块拆分

## 任务清单

1. 创建新的项目结构
2. 代码命名规范化修复
3. 添加类型注解
4. 拆分模块（agent/infrastructure/interfaces）
5. 统一配置管理

## 验证标准（测试用例）

| 编号 | 测试名称 | 前置步骤 | 操作 | 期望结果 |
|------|---------|---------|------|---------|
| TC-1-1 | 项目结构创建 | 无 | 运行 `ls -la agent/ infrastructure/ interfaces/ config/` | 所有目录创建成功，包含`__init__.py`文件 |
| TC-1-2 | Pylint代码检查 | 代码已重构 | 运行 `pylint agent/ infrastructure/ interfaces/ --fail-under=8.0` | 退出码为0，评分≥8.0 |
| TC-1-3 | Mypy类型检查 | 添加类型注解后 | 运行 `mypy agent/ infrastructure/ interfaces/` | 无类型错误报告 |
| TC-1-4 | 模块导入测试 | 所有模块创建完成 | 运行Python `from agent import core; from infrastructure import llm; from interfaces import base` | 导入成功，无ImportError |
| TC-1-5 | 配置文件迁移 | 创建新配置文件 | 运行 `ls config/*.json` | 存在default.json, development.json, mcp_servers.json |
| TC-1-6 | 配置加载测试 | 配置文件已创建 | 运行 `from infrastructure.config.settings import Settings; s = Settings()` | 配置正确加载，无异常 |
| TC-1-7 | 命名规范检查 | 代码重构后 | 运行 `grep -r "memary\|satrtChat" agent/ infrastructure/` | 无结果（已修复拼写错误） |
| TC-1-8 | 导入顺序检查 | 代码规范化后 | 随机抽查5个文件 | 导入顺序符合PEP 8（标准库→第三方→本地） |

## 详细步骤

### Step 1.1: 创建新项目结构

```bash
# 在 termbot 目录下创建新的目录结构
mkdir -p agent/{tools,memory,prompts}
mkdir -p infrastructure/{llm,terminal,mcp,memory,config}
mkdir -p interfaces
mkdir -p config
mkdir -p data
mkdir -p logs
mkdir -p tests

# 创建__init__.py文件
touch agent/__init__.py
touch agent/tools/__init__.py
touch agent/memory/__init__.py
touch agent/prompts/__init__.py
touch infrastructure/__init__.py
touch infrastructure/llm/__init__.py
touch infrastructure/terminal/__init__.py
touch infrastructure/mcp/__init__.py
touch infrastructure/memory/__init__.py
touch infrastructure/config/__init__.py
touch interfaces/__init__.py
```

### Step 1.2: 代码规范修复

#### 修复拼写错误
- `memary` → `memory`
- `satrtChat` → `startChat`
- 其他拼写错误

#### 添加类型注解
```python
# 示例
def process_message(self, message: str) -> str:
    """处理用户消息"""
    pass
```

#### 统一导入顺序
```python
# 1. 标准库
import os
import sys
from typing import Optional

# 2. 第三方库
from openai import OpenAI
from flask import Flask

# 3. 本地模块
from agent.core import Agent
from infrastructure.config.settings import Settings
```

#### 添加文档字符串
```python
class Agent:
    """Agent核心类，与交互层解耦"""

    def process_message(self, message: str) -> str:
        """
        处理用户消息

        Args:
            message: 用户输入的消息

        Returns:
            Agent的响应
        """
        pass
```

### Step 1.3: 配置统一

#### 创建配置文件结构

```
config/
├── default.json         # 默认配置
├── development.json     # 开发环境配置
├── production.json      # 生产环境配置
└── mcp_servers.json     # MCP服务器配置
```

#### 配置示例

```json
// config/default.json
{
  "agent": {
    "max_iterations": 20,
    "enable_memory": true,
    "enable_mcp": true
  },
  "llm": {
    "provider": "openai",
    "api_key": "${OPENAI_API_KEY}",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4",
    "temperature": 0.7
  },
  "terminal": {
    "shell": "/bin/bash",
    "default_cols": 80,
    "default_rows": 24
  },
  "memory": {
    "database_path": "data/termbot.db",
    "vector_db_path": "data/faiss"
  },
  "mcp": {
    "config_file": "config/mcp_servers.json"
  },
  "logging": {
    "level": "INFO",
    "file": "logs/termbot.log"
  }
}
```

```json
// config/mcp_servers.json
{
  "servers": [
    {
      "name": "filesystem",
      "type": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"],
      "enabled": true
    },
    {
      "name": "github",
      "type": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "enabled": false
    }
  ]
}
```

#### 实现配置加载类

```python
# infrastructure/config/settings.py
import json
import os
from typing import Dict, Any
from pathlib import Path


class Settings:
    """配置管理类"""

    def __init__(self, env: str = "default"):
        self.env = env
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        config_path = Path(f"config/{self.env}.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 替换环境变量
        config = self._replace_env_vars(config)
        return config

    def _replace_env_vars(self, config: Any) -> Any:
        """递归替换配置中的环境变量"""
        if isinstance(config, str):
            if config.startswith("${") and config.endswith("}"):
                env_var = config[2:-1]
                return os.getenv(env_var, config)
            return config
        elif isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        return config

    def get(self, key: str, default=None) -> Any:
        """获取配置值，支持点号分隔的路径"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    @property
    def agent(self) -> Dict[str, Any]:
        return self._config.get("agent", {})

    @property
    def llm(self) -> Dict[str, Any]:
        return self._config.get("llm", {})

    @property
    def terminal(self) -> Dict[str, Any]:
        return self._config.get("terminal", {})

    @property
    def memory(self) -> Dict[str, Any]:
        return self._config.get("memory", {})
```

## 验收检查表

- [ ] 项目结构创建完成
- [ ] 代码通过`pylint`检查
- [ ] 代码通过`mypy`检查
- [ ] 配置文件迁移完成
- [ ] 所有模块可正常导入
- [ ] 命名规范错误已修复
- [ ] 导入顺序符合PEP 8
- [ ] 类型注解添加完成

## 估计工作量

3-4天
