# 阶段三：LLM调用优化与终端管理

## 目标

优化LLM调用方式，改进终端管理

## 任务清单

1. 实现标准Function Calling（`infrastructure/llm/function_calling.py`）
2. 重构React循环使用Function Calling
3. 实现PTY管理器（`infrastructure/terminal/pty_manager.py`）
   - 实现PTYInputLock输入锁机制
   - 实现输出监听器注册/通知机制
4. 实现Web和Agent的监听器集成
5. 优化提示词（可选英文）

## 验证标准（测试用例）

| 编号 | 测试名称 | 前置步骤 | 操作 | 期望结果 |
|------|---------|---------|------|---------|
| TC-3-1 | Function Calling格式 | function_calling.py已实现 | 运行 `client.chat(messages, tools)` | 返回包含`tool_calls`的标准格式 |
| TC-3-2 | 工具调用解析 | FunctionCall类已实现 | 运行 `FunctionCall.from_response(response)` | 正确解析工具名和参数 |
| TC-3-3 | PTY管理器启动 | PTYManager已实现 | 运行 `mgr.start()` | 进程启动，pty fork成功 |
| TC-3-4 | 输入锁机制 | PTYInputLock已实现 | 运行 `lock.acquire("test"); lock.is_locked()` | 锁成功获取，is_locked返回True |
| TC-3-5 | 输入锁释放 | PTYInputLock已实现 | 运行 `lock.acquire("owner"); lock.release("owner")` | 锁成功释放，可再次获取 |
| TC-3-6 | 输入锁超时 | PTYInputLock已实现 | 运行 `lock.acquire("a"); lock.acquire("b", timeout=1)` | 第二个获取超时，返回失败 |
| TC-3-7 | 输出监听器注册 | PTYManager已实现 | 运行 `mgr.register_listener(callback)` | 监听器注册成功 |
| TC-3-8 | 输出监听器通知 | PTYManager已实现 | 注册监听器后写入PTY | 监听器回调被调用，收到输出 |
| TC-3-9 | 多监听器隔离 | PTYManager已实现 | 注册Web和Agent两个监听器 | 两者都收到通知，互不干扰 |
| TC-3-10 | Web集成测试 | WebHandler已实现 | 启动Web，用户键盘输入 | xterm.js显示输出 |
| TC-3-11 | LLM调用次数对比 | 前后版本已部署 | 执行相同任务，记录LLM调用次数 | 新版本调用次数≤旧版本70% |
| TC-3-12 | 提示词模板加载 | prompts/templates.txt已创建 | 运行 `get_prompt("react_loop", tools=[])` | 返回渲染后的提示词 |
| TC-3-13 | React循环集成 | Function Calling已集成 | 运行 `agent.process_message("查看当前目录")` | 自动调用exec_terminal_cmd工具 |
| TC-3-14 | 提示词格式验证 | 所有提示词已迁移 | 运行 `validate_all_prompts()` | 所有提示词格式一致，无语法错误 |

## 核心设计

### 3.1 终端管理器架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                           PTYManager                                 │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  输入锁 (PTYInputLock)                                         │ │
│  │  - acquire_lock(timeout) → 等待/成功/超时                      │ │
│  │  - write(data, owner) → 写入PTY                                │ │
│  │  - release_lock(owner) → 释放锁                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  输出监听器 (观察者模式)                                        │ │
│  │  - register_listener(callback) → 注册监听                     │ │
│  │  - _notify_listeners(data) → 通知所有监听器                   │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ PTY输出
              ┌────────────┴────────────┐
              ↓                         ↓
    ┌─────────────────┐       ┌─────────────────┐
    │  WebListener    │       │  AgentListener  │
    │  → xterm.js     │       │  → 内部缓冲区   │
    └─────────────────┘       │  → 自己解析     │
                              └─────────────────┘
```

### 3.2 PTY管理器实现

```python
# infrastructure/terminal/pty_manager.py
import os
import pty
import select
import threading
import time
from typing import Callable, List, Optional
from dataclasses import dataclass


@dataclass
class LockResult:
    """加锁结果"""
    success: bool
    message: str = ""


class PTYInputLock:
    """PTY输入锁 - 保证同一时间只有一个写入者"""

    def __init__(self, timeout: int = 30):
        self._locked = False
        self._owner: Optional[str] = None
        self._timeout = timeout

    def acquire(self, owner: str, timeout: Optional[int] = None) -> LockResult:
        """获取锁，阻塞等待直到超时"""
        timeout = timeout or self._timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not self._locked:
                self._locked = True
                self._owner = owner
                return LockResult(True, f"Lock acquired by {owner}")
            time.sleep(0.1)

        return LockResult(False, f"Lock acquisition timeout after {timeout}s")

    def release(self, owner: str) -> LockResult:
        """释放锁"""
        if self._owner == owner:
            self._locked = False
            self._owner = None
            return LockResult(True, "Lock released")
        return LockResult(False, f"Lock not owned by {owner}")

    def is_locked(self) -> bool:
        return self._locked

    @property
    def owner(self) -> Optional[str]:
        return self._owner


class PTYManager:
    """PTY管理器 - 统一管理PTY的输入输出"""

    def __init__(self, shell: str = "/bin/bash", cols: int = 80, rows: int = 24):
        self.shell = shell
        self.cols = cols
        self.rows = rows
        self.pid: Optional[int] = None
        self.fd: Optional[int] = None
        self._running = False

        # 输入锁
        self._input_lock = PTYInputLock(timeout=30)

        # 输出监听器列表
        self._listeners: List[Callable[[str], None]] = []
        self._read_thread: Optional[threading.Thread] = None

    def start(self):
        """启动PTY"""
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            # 子进程
            os.execv(self.shell, [self.shell])

        self._running = True
        self._start_read_thread()

    def _start_read_thread(self):
        """启动读取线程"""
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def _read_loop(self):
        """读取循环 - 持续从PTY读取并通知所有监听器"""
        while self._running:
            try:
                r, _, _ = select.select([self.fd], [], [], 0.1)
                if r:
                    data = os.read(self.fd, 1024)
                    if not data:
                        break
                    text = data.decode('utf-8', errors='replace')
                    # 通知所有监听器
                    self._notify_listeners(text)
            except OSError:
                break

    def register_listener(self, callback: Callable[[str], None]):
        """注册输出监听器"""
        self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[str], None]):
        """取消注册监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, data: str):
        """通知所有监听器（单个监听器异常不影响其他）"""
        for listener in self._listeners:
            try:
                listener(data)
            except Exception as e:
                print(f"Listener error: {e}")

    def write(self, data: str, owner: str) -> LockResult:
        """
        写入数据到PTY（需要先加锁）

        Args:
            data: 要写入的数据
            owner: 写入者标识（如 "web_session_123" 或 "agent_tool"）

        Returns:
            LockResult: 操作结果
        """
        # 先尝试加锁
        lock_result = self._input_lock.acquire(owner)
        if not lock_result.success:
            return lock_result

        try:
            # 加锁成功，执行写入
            if self.fd:
                os.write(self.fd, data.encode('utf-8'))
            return LockResult(True, "Write successful")
        finally:
            # 完成后释放锁
            self._input_lock.release(owner)

    def write_with_lock_held(self, data: str) -> bool:
        """
        在已持有锁的情况下写入（内部方法）

        注意: 调用此方法前必须已经持有锁
        """
        if self.fd:
            os.write(self.fd, data.encode('utf-8'))
            return True
        return False

    def resize(self, cols: int, rows: int):
        """调整终端大小"""
        if self.fd:
            import fcntl
            import struct
            import termios
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    def stop(self):
        """停止PTY"""
        self._running = False
        if self.fd:
            os.close(self.fd)
        if self.pid:
            os.kill(self.pid, 9)

    @property
    def lock_owner(self) -> Optional[str]:
        """获取当前锁持有者"""
        return self._input_lock.owner

    def is_locked(self) -> bool:
        """检查是否被锁定"""
        return self._input_lock.is_locked()
```

### 3.3 Web集成示例

```python
# interfaces/web.py
from flask_socketio import SocketIO, emit

class WebHandler:
    """Web交互层"""

    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.pty_manager = PTYManager()

        # 注册Web监听器 - 将PTY输出推送到前端
        self.pty_manager.register_listener(self._on_terminal_output)

        # 启动PTY
        self.pty_manager.start()

    def _on_terminal_output(self, data: str):
        """PTY输出回调 - 推送到前端xterm.js"""
        self.socketio.emit('terminal_output', {'data': data})

    def handle_user_input(self, data: str, sid: str):
        """处理用户键盘输入"""
        owner = f"web_{sid}"
        result = self.pty_manager.write(data, owner=owner)

        if not result.success:
            # 加锁失败（可能是Agent正在操作）
            emit('terminal_error', {'message': result.message})
```

### 3.4 Agent工具集成示例

```python
# agent/tools/terminal.py
from agent.tools.base import Tool, ToolSchema, ToolParameter, ToolParameterType

class TerminalTool(Tool):
    """终端命令执行工具"""

    def __init__(self, pty_manager: PTYManager):
        self.pty_manager = pty_manager
        self.owner_id = f"agent_{id(self)}"

        # 注册Agent监听器 - 收集命令输出供分析
        self.pty_manager.register_listener(self._on_terminal_output)

        # Agent自己的输出缓冲区
        self._buffer = []
        self._collecting = False

    def _on_terminal_output(self, data: str):
        """PTY输出回调 - Agent内部处理"""
        if self._collecting:
            self._buffer.append(data)

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="exec_terminal_cmd",
            description="Execute a command in the terminal and return the output",
            parameters=[
                ToolParameter(
                    name="command",
                    type=ToolParameterType.STRING,
                    description="The command to execute",
                    required=True
                )
            ]
        )

    def execute(self, command: str) -> str:
        """执行终端命令"""
        # 1. 尝试加锁（超时30秒）
        lock_result = self.pty_manager._input_lock.acquire(
            self.owner_id,
            timeout=30
        )

        if not lock_result.success:
            return f"Failed to acquire terminal lock: {lock_result.message}"

        try:
            # 2. 开始收集输出
            self._collecting = True
            self._buffer = []

            # 3. 执行命令
            self.pty_manager.write_with_lock_held(command + "\n")

            # 4. 等待命令完成
            import time
            time.sleep(1)

            # 5. 停止收集并返回结果
            self._collecting = False
            output = ''.join(self._buffer)

            return output if output else "(command executed with no output)"

        finally:
            # 6. 释放锁
            self.pty_manager._input_lock.release(self.owner_id)
```

### 3.5 Function Calling实现

```python
# infrastructure/llm/function_calling.py
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class FunctionCall:
    """函数调用"""
    name: str
    arguments: Dict[str, Any]

    @classmethod
    def from_response(cls, response: Any) -> Optional['FunctionCall']:
        """从LLM响应解析Function Call"""
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_call = response.tool_calls[0]
            return cls(
                name=tool_call.function.name,
                arguments=eval(tool_call.function.arguments)  # JSON to dict
            )
        return None
```

### 3.6 提示词优化

```python
# agent/prompts/templates.txt
::prompt
react_loop
::content
You are an intelligent terminal assistant that helps users accomplish tasks through terminal commands.

## Available Tools
{% for tool in tools %}
- {{ tool.name }}: {{ tool.description }}
{% endfor %}

## Terminal Content
{% if terminal_content %}
```
{{ terminal_content }}
```
{% endif %}

## Task Progress
{% if done_steps %}
### Completed Steps:
{% for step in done_steps %}
- {{ step }}
{% endfor %}
{% endif %}

{% if pending_steps %}
### Pending Steps:
{% for step in pending_steps %}
- {{ step }}
{% endfor %}
{% endif %}

## User Task
{{ user_task }}

## Instructions
1. Analyze the current situation
2. Decide if you need to use a tool or respond directly
3. If using a tool, provide the tool name and arguments
4. If responding directly, provide a helpful answer

## Response Format
Return a JSON object with the following structure:
```json
{
  "thought": "Your reasoning about what to do next",
  "tool_name": "Name of the tool to use (or null)",
  "tool_args": {"argument": "value"}  // if tool_name is provided
}
```

作为智能终端助手，严格遵守上述格式，分析用户任务并提供合适的响应。
```

## 架构优势

| 优势 | 说明 |
|------|------|
| **统一管理** | PTY输入输出都在PTYManager中管理 |
| **避免冲突** | 通过锁机制保证同一时间只有一个写入者 |
| **模块解耦** | Web、Agent各自处理自己的逻辑，互不干扰 |
| **易于扩展** | 新增监听器只需注册即可（如日志模块、审计模块） |
| **问题隔离** | Agent处理vim的困难不影响Web显示 |
| **用户反馈** | 当Agent正在操作时，用户输入会得到明确的超时提示 |

## 待优化问题

| 问题 | 当前方案 | 后续优化方向 |
|------|---------|-------------|
| **命令完成检测** | 固定sleep等待 | 检测shell提示符（$、#等） |
| **锁超时处理** | 简单超时返回 | 前端显示繁忙状态，允许用户"抢断" |
| **交互式程序** | Agent暂不处理 | 检测终端模式变化，跳过全屏程序 |
| **多标签支持** | 未涉及 | 每个标签独立的PTY实例 |

## 详细步骤

### Step 3.1: 实现PTYInputLock
创建 `infrastructure/terminal/pty_manager.py`，实现输入锁机制

### Step 3.2: 实现PTYManager
实现PTY管理器和监听器机制

### Step 3.3: 实现Function Calling
创建 `infrastructure/llm/function_calling.py`

### Step 3.4: 集成到React循环
修改 ReactLoop 使用 Function Calling

### Step 3.5: 集成Web监听器
修改 WebHandler 使用新的 PTYManager

### Step 3.6: 集成Agent监听器
修改 TerminalTool 使用新的 PTYManager

### Step 3.7: 优化提示词
将提示词迁移到新格式并优化

## 验收检查表

- [ ] Function Calling实现完成
- [ ] PTYInputLock输入锁实现完成
- [ ] 输出监听器机制实现完成
- [ ] Web监听器集成完成
- [ ] Agent监听器集成完成
- [ ] 多监听器隔离验证通过
- [ ] LLM调用优化完成
- [ ] 提示词优化完成

## 估计工作量

4-5天
