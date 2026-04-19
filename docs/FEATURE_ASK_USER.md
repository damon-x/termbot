# Agent 用户交互增强：ask_user 功能

## 一、需求概述

### 1.1 功能描述

让 Agent 在执行任务过程中，当需要询问用户时可以停下来等待用户回复，然后再继续任务。

**核心场景：**
- Agent 执行危险操作前需要确认（如"确认删除文件吗？"）
- Agent 需要用户提供必要信息（如"请提供文件路径"）
- Agent 需要用户在多个选项中选择（如"选择部署环境：dev/prod"）

### 1.2 当前状态

**已有基础设施：**
- `Context` 已有 `_waiting_user_answer` 和 `_user_answer` 字段
- `Context` 已有 `pause_chat()` / `is_paused()` 等方法
- `Agent` 已暴露 `is_paused()` 和 `provide_user_answer()` 方法

**缺失部分：**
- ❌ `ask_user` Tool 未实现
- ❌ `ReactLoop` 不支持暂停/恢复
- ❌ `ReactResult` 缺少状态字段
- ❌ Interface 层未处理暂停状态

---

## 二、架构设计

### 2.1 整体流程图

```
┌─────────────────────────────────────────────────────────────────┐
│ 用户发送消息: "删除 /tmp 目录"                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ ReactLoop.run() - ReAct 循环                                      │
│                                                                  │
│  Iteration 1:                                                    │
│    Thought: 需要确认用户是否真的要删除                             │
│    Action: ask_user("确认删除 /tmp 吗？", ["yes", "no"])          │
│    Observation: __ASK_USER_PENDING__                              │
│                                                                  │
│  ← 检测到暂停标记，返回 ReactResult(status="paused")              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Interface 层收到 ReactResult                                      │
│                                                                  │
│  CLI:                                                           │
│    - 显示 "❓ 确认删除 /tmp 吗？"                                 │
│    - 显示 "选项: yes/no"                                          │
│    - 等待用户输入                                                 │
│                                                                  │
│  Web:                                                           │
│    - emit('chat_out', {type: 'question', question: ...})         │
│    - 前端显示问题对话框或选项                                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 用户输入: "yes"                                                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Interface 层:                                                   │
│   - agent.provide_user_answer("yes")                             │
│   - agent.resume_task() 或继续 run()                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ ReactLoop.run() - 恢复 ReAct 循环                                 │
│                                                                  │
│  Iteration 2:                                                    │
│    用户的回答 "yes" 已在消息历史中                                │
│    Thought: 用户确认了，执行删除操作                                │
│    Action: exec_terminal_cmd("rm -rf /tmp")                      │
│    Observation: 删除完成                                          │
│                                                                  │
│  Iteration 3:                                                    │
│    Thought: 任务完成                                              │
│    Action: (无，直接回复)                                         │
│    Response: /tmp 目录已删除                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件职责

| 组件 | 新增职责 | 不做什么 |
|------|---------|---------|
| **`ask_user` Tool** | 设置 Context 状态，返回特殊标记 | 不等待、不与 Interface 直接交互 |
| **`ReactLoop`** | 检测暂停标记，返回 `status="paused"` | 不处理 UI 显示 |
| **`ReactResult`** | 新增 `status`, `question`, `options` 字段 | - |
| **`Agent`** | 新增 `resume_task()` 方法 | 不处理 UI 逻辑 |
| **`Context`** | 复用现有字段，新增 `pending_question` 状态存储 | - |
| **`Interface`** | 检测 paused 状态，显示问题，处理用户回复 | 不执行业务逻辑 |

---

## 三、详细实现方案

### 3.1 `ask_user` Tool (`agent/tools/impl.py`)

**新增代码：**

```python
def register_ask_user_tool(agent: 'Agent') -> None:
    """
    注册 ask_user 工具。

    Args:
        agent: Agent 实例（用于访问 Context）
    """

    def ask_user(question: str, options: Optional[List[str]] = None) -> str:
        """
        询问用户一个问题并暂停执行。

        当 Agent 需要用户确认或提供信息时使用此工具。
        调用后，Agent 会暂停执行，等待用户回复后继续。

        Args:
            question: 要问用户的问题
            options: 可选的选项列表，如 ["yes", "no", "cancel"]
                     如果提供，用户应从选项中选择

        Returns:
            特殊标记，通知 ReactLoop 暂停执行

        Example:
            ask_user("确认删除吗？", ["yes", "no"])
            ask_user("请提供部署服务器地址")
        """
        context = agent.get_context()

        # 1. 存储问题信息到 Context（供 Interface 读取）
        context.set_state("pending_question", {
            "question": question,
            "options": options
        })

        # 2. 标记为等待用户答案
        context.set_waiting_user_answer(True)

        # 3. 返回特殊标记
        return "__ASK_USER_PENDING__"

    tool = SimpleTool(
        name="ask_user",
        description="询问用户问题并暂停执行，等待用户回复后继续",
        function=ask_user
    )

    agent.register_tool(tool)
```

### 3.2 `ReactLoop` 修改 (`agent/react.py`)

**修改 `ReactResult` 数据类：**

```python
@dataclass
class ReactResult:
    """Result of running the ReAct loop."""
    response: str
    steps: List[ReactStep] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    # 新增字段
    status: str = "success"  # "success" / "paused" / "failed"
    question: Optional[str] = None
    options: Optional[List[str]] = None
```

**修改 `run()` 方法：**

```python
# 在 _execute_function_call 之后添加检测

if response.function_call:
    step = self._execute_function_call(response.function_call)
    steps.append(step)

    # 新增：检测是否是 ask_user 触发的暂停
    if step.observation == "__ASK_USER_PENDING__":
        question_data = self.context.get_state("pending_question", {})
        self.context.add_message("tool", "Waiting for user input...")
        self.context.set_status("paused")

        return ReactResult(
            response="需要您的回复才能继续",
            steps=steps,
            status="paused",
            question=question_data.get("question"),
            options=question_data.get("options")
        )

    # ... 原有的 observation 添加逻辑 ...
```

**新增 `resume()` 方法：**

```python
def resume(self) -> ReactResult:
    """
    从暂停点恢复执行。

    调用前应确保：
    1. 用户答案已通过 Context.set_user_answer() 设置
    2. 用户答案已作为消息添加到历史

    Returns:
        ReactResult with the final response
    """
    if not self.context.is_waiting_user_answer():
        raise RuntimeError("Cannot resume: agent is not paused")

    # 用户的答案已经在 provide_user_answer 中添加到消息历史了
    # 这里直接继续 ReAct 循环
    self.context.set_status("running")

    steps: List[ReactStep] = []

    for iteration in range(self.max_iterations):
        tools = self.tool_registry.get_tool_schemas()
        messages = self._build_messages()

        try:
            response = self.llm_client.chat_with_tools(
                messages=messages,
                tools=tools if tools else None
            )
        except Exception as e:
            return ReactResult(
                response=f"Error communicating with LLM: {e}",
                steps=steps,
                success=False,
                error=str(e),
                status="failed"
            )

        # ... 后续逻辑与 run() 相同 ...
```

### 3.3 `Agent` 修改 (`agent/core.py`)

**新增方法：**

```python
def process_message_with_result(self, message: str) -> ReactResult:
    """
    Process a user message and return the full result.

    Args:
        message: User's input message

    Returns:
        Complete ReactResult with steps and metadata
    """
    return self.react_loop.run(message)

def resume_task(self) -> ReactResult:
    """
    从暂停点恢复任务执行。

    调用前应先调用 provide_user_answer() 设置用户答案。

    Returns:
        ReactResult with the final response

    Raises:
        RuntimeError: 如果 Agent 不处于暂停状态
    """
    return self.react_loop.resume()
```

### 3.4 `Context` 修改 (`agent/context.py`)

**可选：新增辅助方法**

```python
def get_pending_question(self) -> Optional[Dict[str, Any]]:
    """
    获取待处理的问题信息。

    Returns:
        问题信息字典，包含 'question' 和 'options'，如果没有则返回 None
    """
    return self._state.get("pending_question")
```

### 3.5 CLI Interface 修改 (`interfaces/cli.py`)

**修改 `send_message()` 和 `run_session()`：**

```python
def send_message(self, message: str) -> str:
    """Send message and handle pause/resume."""
    result = self.agent.process_message_with_result(message)

    # 处理暂停状态
    while result.status == "paused":
        # 显示问题
        print(f"\n❓ {result.question}")
        if result.options:
            print(f"选项: {' / '.join(result.options)}")

        # 获取用户输入
        while True:
            answer = input("\n🧑 Your answer: ").strip()

            # 验证选项（如果有）
            if result.options and answer not in result.options:
                print(f"⚠️ 请从选项中选择: {result.options}")
                continue

            break

        # 提供答案并恢复
        self.agent.provide_user_answer(answer)
        result = self.agent.resume_task()

    if result.success:
        return result.response
    return f"Error: {result.error or 'Unknown error'}"
```

### 3.6 Web Interface 修改 (`interfaces/web.py`)

**修改 `handle_chat_message()` 事件处理器：**

```python
@self.socketio.on('chat_in')
def handle_chat_message(data):
    """Handle chat message from client."""
    sid = request.sid
    message = data.get('message', '').strip()

    if not message:
        return

    if sid not in self.sessions:
        self.socketio.emit('chat_out', {'message': 'Session not found. Please refresh.'}, room=sid)
        return

    session = self.sessions[sid]

    # 检查是否在等待用户回复
    if session.agent.is_paused():
        # 用户在回答之前的问题
        session.agent.provide_user_answer(message)
        result = session.agent.resume_task()
    else:
        # 正常处理新消息
        if message.startswith("/"):
            response = self._handle_command(message, session)
            self.socketio.emit('chat_out', {'message': response}, room=sid)
            return
        else:
            result = session.agent.process_message_with_result(message)

    # 根据 status 决定返回内容
    if result.status == "paused":
        # 发送问题到前端
        self.socketio.emit('chat_out', {
            'type': 'question',
            'message': result.response,
            'question': result.question,
            'options': result.options or []
        }, room=sid)
    else:
        # 正常响应
        self.socketio.emit('chat_out', {
            'type': 'response',
            'message': result.response
        }, room=sid)
```

---

## 四、实现步骤

### Phase 1: 核心改动 (优先)

| 序号 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 1.1 | `ReactResult` 新增 `status`, `question`, `options` 字段 | `agent/react.py` | 0.5h |
| 1.2 | 实现 `ask_user` Tool | `agent/tools/impl.py` | 1h |
| 1.3 | `ReactLoop.run()` 添加暂停检测逻辑 | `agent/react.py` | 1h |
| 1.4 | `ReactLoop` 新增 `resume()` 方法 | `agent/react.py` | 1.5h |
| 1.5 | `Agent` 新增 `resume_task()` 方法 | `agent/core.py` | 0.5h |

**总计：4.5h**

### Phase 2: Interface 层适配

| 序号 | 任务 | 文件 | 工作量 |
|------|------|------|--------|
| 2.1 | CLI `send_message()` 支持暂停处理 | `interfaces/cli.py` | 1h |
| 2.2 | Web `handle_chat_message()` 支持暂停处理 | `interfaces/web.py` | 1.5h |
| 2.3 | 前端适配（处理 `type: 'question'` 消息） | `static/index.html` | 1h |

**总计：3.5h**

### Phase 3: 测试与优化

| 序号 | 任务 | 工作量 |
|------|------|--------|
| 3.1 | 单元测试：ask_user Tool | 1h |
| 3.2 | 单元测试：ReactLoop 暂停/恢复 | 1h |
| 3.3 | 集成测试：CLI 场景 | 0.5h |
| 3.4 | 集成测试：Web 场景 | 0.5h |
| 3.5 | 边界情况测试（连续 ask_user, 超时等） | 1h |

**总计：4h**

---

## 五、测试用例

### 5.1 单元测试

```python
# tests/unit/test_ask_user_tool.py
def test_ask_user_sets_context_state():
    """Test that ask_user sets correct context state."""
    agent = create_test_agent()
    context = agent.get_context()

    # Execute ask_user
    tool = agent.get_tool("ask_user")
    result = tool.execute(question="确认吗？", options=["yes", "no"])

    # Verify
    assert result == "__ASK_USER_PENDING__"
    assert context.is_waiting_user_answer()
    question_data = context.get_state("pending_question")
    assert question_data["question"] == "确认吗？"
    assert question_data["options"] == ["yes", "no"]

def test_react_loop_pause_on_ask_user():
    """Test that ReactLoop pauses when ask_user is called."""
    agent = create_test_agent()

    result = agent.process_message_with_result("测试暂停")

    assert result.status == "paused"
    assert result.question == "确认吗？"
    assert result.options == ["yes", "no"]

def test_react_loop_resume_after_answer():
    """Test that ReactLoop resumes after user provides answer."""
    agent = create_test_agent()

    # First call triggers pause
    result1 = agent.process_message_with_result("测试暂停")
    assert result1.status == "paused"

    # Provide answer and resume
    agent.provide_user_answer("yes")
    result2 = agent.resume_task()

    assert result2.status == "success"
    assert "yes" in result2.response
```

### 5.2 集成测试场景

| 场景 | 输入 | 预期行为 |
|------|------|---------|
| 简单确认 | "删除文件" | Agent 调用 ask_user，等待确认 |
| 带选项确认 | "部署环境" | Agent 提供选项，用户选择后执行 |
| 多次询问 | "复杂任务" | 可能连续调用 ask_user |
| 非暂停任务 | "列出文件" | 正常执行，不暂停 |
| 超时处理 | 暂停后长时间不回复 | 可选：自动取消或超时 |

---

## 六、依赖关系

```
ask_user Tool
    ↓
ReactLoop 暂停检测
    ↓
ReactResult 状态字段
    ↓
Agent.resume_task()
    ↓
Interface 层处理
```

**必须按顺序实现 Phase 1 的所有任务后，才能开始 Phase 2。**

---

## 七、风险与注意事项

### 7.1 风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| ReactLoop 状态管理复杂化 | 可能引入 bug | 充分测试，添加状态转换日志 |
| Interface 层兼容性 | 前端需要适配 | 提供清晰的协议文档 |
| 用户长时间不回复 | 资源占用 | 可选：添加暂停超时机制 |
| 嵌套 ask_user 调用 | 状态混乱 | 限制同时只能有一个未回答问题 |

### 7.2 设计约束

- **暂停不是阻塞**：Tool 不应等待用户输入，而是立即返回标记
- **Context 是桥梁**：问题信息通过 Context 传递，不直接耦合 Interface
- **用户答案是消息**：用户的回复应作为 `user` 消息添加到历史，保持对话连贯性
- **幂等性**：`resume_task()` 如果不在暂停状态应抛出异常

---

## 八、后续增强

- [ ] 支持超时自动取消（如 5 分钟不回复则取消任务）
- [ ] 支持 ask_user 的富文本格式（Markdown、图片等）
- [ ] 支持批量问题（一次问多个相关问题）
- [ ] 支持 `ask_user` 的历史记录（查看之前问过的问题）
- [ ] 前端 UI 优化（专门的问答组件）
