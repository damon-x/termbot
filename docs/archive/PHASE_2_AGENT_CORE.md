# 阶段二：Agent核心解耦

## 目标

Agent核心逻辑与交互层分离

## 任务清单

1. 实现新的Agent核心类（`agent/core.py`）
2. 重构React循环（`agent/react.py`）
3. 实现工具基类和工具注册机制（`agent/tools/base.py`）
4. 迁移现有工具到新架构
5. 实现交互层抽象（`interfaces/base.py`）

## 验证标准（测试用例）

| 编号 | 测试名称 | 前置步骤 | 操作 | 期望结果 |
|------|---------|---------|------|---------|
| TC-2-1 | Agent依赖检查 | Agent类已实现 | 运行 `grep -r "flask\|socketio" agent/core.py agent/react.py` | 无结果（不依赖Flask） |
| TC-2-2 | Agent独立导入 | 无Flask环境 | 运行Python `from agent.core import Agent; a = Agent(config)` | 导入和实例化成功 |
| TC-2-3 | Agent基础功能 | Agent已创建 | 运行 `agent.process_message("你好")` | 返回字符串响应 |
| TC-2-4 | 工具注册测试 | ToolRegistry已实现 | 运行 `registry.register(tool); registry.list_tools()` | 工具成功注册，名称在列表中 |
| TC-2-5 | 工具Schema验证 | 工具已实现 | 运行 `tool.schema.to_dict()` | 返回标准OpenAI Function格式 |
| TC-2-6 | React循环测试 | ReactLoop已实现 | 运行 `loop.run("测试消息")` | 返回响应，steps列表有记录 |
| TC-2-7 | Context状态测试 | Context已实现 | 运行 `ctx.add_message(); ctx.get_messages()` | 消息正确添加和获取 |
| TC-2-8 | 单元测试覆盖 | 单元测试已编写 | 运行 `pytest tests/unit/test_agent.py --cov=agent` | 覆盖率≥70% |
| TC-2-9 | 交互层抽象 | base.py已实现 | 运行 `from interfaces.base import BaseHandler` | 基类可导入，子类可实现 |
| TC-2-10 | 无Flask单元测试 | 测试环境无Flask | 运行 `pytest tests/unit/` | 所有Agent单元测试通过 |

## 详细设计

### 2.1 Agent核心类

```python
# agent/core.py
from typing import Optional, Callable, Any
from dataclasses import dataclass, field

from agent.context import Context
from agent.react import ReactLoop
from infrastructure.llm.client import LLMClient
from infrastructure.config.settings import Settings


@dataclass
class AgentConfig:
    """Agent配置"""
    llm_client: LLMClient
    max_iterations: int = 20
    enable_memory: bool = True
    enable_mcp: bool = True


class Agent:
    """Agent核心类，与交互层解耦"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.context = Context()
        self.react_loop = ReactLoop(
            llm_client=config.llm_client,
            context=self.context,
            max_iterations=config.max_iterations
        )
        self._setup_tools()

    def _setup_tools(self):
        """设置可用工具"""
        from agent.tools.terminal import TerminalTool
        from agent.tools.note import NoteTool
        from agent.tools.file import FileTool

        self.react_loop.register_tool(TerminalTool())
        self.react_loop.register_tool(NoteTool())
        self.react_loop.register_tool(FileTool())

        # MCP工具在阶段五实现，暂时注释
        # if self.config.enable_mcp:
        #     from agent.tools.mcp import MCPToolRegistry
        #     mcp_registry = MCPToolRegistry()
        #     mcp_registry.load_from_config()
        #     for tool in mcp_registry.get_tools():
        #         self.react_loop.register_tool(tool)

    def process_message(self, message: str) -> str:
        """处理用户消息"""
        result = self.react_loop.run(message)
        return result

    def get_context(self) -> Context:
        """获取执行上下文"""
        return self.context
```

### 2.2 React循环实现

```python
# agent/react.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from agent.context import Context
from agent.tools.base import Tool, ToolRegistry
from infrastructure.llm.client import LLMClient
from infrastructure.llm.function_calling import FunctionCall


@dataclass
class ReactStep:
    """React步骤"""
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None


class ReactLoop:
    """ReAct循环实现"""

    def __init__(
        self,
        llm_client: LLMClient,
        context: Context,
        max_iterations: int = 20
    ):
        self.llm_client = llm_client
        self.context = context
        self.max_iterations = max_iterations
        self.tool_registry = ToolRegistry()
        self.steps: List[ReactStep] = []

    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tool_registry.register(tool)

    def run(self, user_input: str) -> str:
        """运行ReAct循环"""
        self.context.add_message("user", user_input)

        for iteration in range(self.max_iterations):
            # 1. 思考
            thought = self._think()
            self.steps.append(ReactStep(thought=thought))

            # 2. 决策是否需要使用工具
            function_call = self._decide_action()
            if function_call is None:
                # 直接回复
                response = self._generate_response()
                self.context.add_message("assistant", response)
                return response

            # 3. 执行工具
            step = self.steps[-1]
            step.action = function_call.name
            step.action_input = function_call.arguments

            observation = self._execute_tool(function_call)
            step.observation = observation

            # 4. 判断是否完成
            if self._is_complete(observation):
                final_response = self._generate_final_response()
                self.context.add_message("assistant", final_response)
                return final_response

        # 达到最大迭代次数
        return self._generate_final_response()

    def _think(self) -> str:
        """思考下一步行动"""
        # 实现思考逻辑
        pass

    def _decide_action(self) -> Optional[FunctionCall]:
        """决定是否使用工具"""
        # 使用Function Calling
        tools = self.tool_registry.get_tool_schemas()
        response = self.llm_client.chat(
            messages=self.context.get_messages(),
            tools=tools
        )
        return response.function_call

    def _execute_tool(self, function_call: FunctionCall) -> str:
        """执行工具"""
        tool = self.tool_registry.get(function_call.name)
        result = tool.execute(**function_call.arguments)
        return str(result)

    def _is_complete(self, observation: str) -> bool:
        """判断任务是否完成"""
        # 实现完成判断逻辑
        pass

    def _generate_response(self) -> str:
        """生成响应"""
        pass

    def _generate_final_response(self) -> str:
        """生成最终响应"""
        pass
```

### 2.3 工具基类

```python
# agent/tools/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class ToolParameterType(Enum):
    """工具参数类型"""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: ToolParameterType
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolSchema:
    """工具Schema"""
    name: str
    description: str
    parameters: List[ToolParameter]

    def to_dict(self) -> Dict[str, Any]:
        """转换为OpenAI Function格式"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type.value,
                "description": param.description
            }
            if param.default is not None:
                properties[param.name]["default"] = param.default
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class Tool(ABC):
    """工具基类"""

    @property
    @abstractmethod
    def schema(self) -> ToolSchema:
        """获取工具Schema"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """执行工具"""
        pass


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.schema.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的Schema"""
        return [tool.schema.to_dict() for tool in self._tools.values()]

    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())
```

### 2.4 交互层抽象

```python
# interfaces/base.py
from abc import ABC, abstractmethod
from typing import Callable, Optional

from agent.core import Agent


class BaseHandler(ABC):
    """交互层基类"""

    def __init__(self, agent: Agent):
        self.agent = agent

    @abstractmethod
    def start(self):
        """启动交互"""
        pass

    @abstractmethod
    def stop(self):
        """停止交互"""
        pass

    @abstractmethod
    def send_message(self, message: str) -> str:
        """发送消息并获取响应"""
        pass

    @abstractmethod
    def on_agent_response(self, response: str):
        """Agent响应回调"""
        pass
```

### 2.5 上下文管理

```python
# agent/context.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Message:
    """消息"""
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class Context:
    """执行上下文"""

    def __init__(self):
        self._messages: List[Message] = []
        self._state: Dict[str, Any] = {}

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """添加消息"""
        message = Message(role=role, content=content, metadata=metadata or {})
        self._messages.append(message)

    def get_messages(self) -> List[Dict[str, str]]:
        """获取消息列表（用于LLM）"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self._messages
        ]

    def clear_messages(self):
        """清空消息"""
        self._messages.clear()

    def set_state(self, key: str, value: Any):
        """设置状态"""
        self._state[key] = value

    def get_state(self, key: str, default=None) -> Any:
        """获取状态"""
        return self._state.get(key, default)

    @property
    def message_count(self) -> int:
        """消息数量"""
        return len(self._messages)
```

## 详细步骤

### Step 2.1: 实现Context类

创建 `agent/context.py`，实现对话状态管理

### Step 2.2: 实现工具基类

创建 `agent/tools/base.py`，定义工具接口

### Step 2.3: 实现React循环

创建 `agent/react.py`，重构ReAct逻辑

### Step 2.4: 实现Agent核心类

创建 `agent/core.py`，组装各组件

### Step 2.5: 实现交互层抽象

创建 `interfaces/base.py`，定义交互层接口

### Step 2.6: 迁移现有工具

将现有工具迁移到新架构：
- `bot/tools.py` → `agent/tools/`
- `bot/ability/basic.py` 中的工具 → `agent/tools/`

## 验收检查表

- [ ] Agent类实现完成
- [ ] React循环实现完成
- [ ] 工具系统实现完成
- [ ] 单元测试通过
- [ ] Agent与Flask解耦
- [ ] Context状态管理正常
- [ ] 工具注册机制正常
- [ ] 交互层抽象可继承

## 估计工作量

4-5天
