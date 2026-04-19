# TermBot 待办事项与产品规划

## 一、上下文工程（Prompt Engineering）问题清单

### 1.1 模板系统未充分利用

**问题**: 新的 `ReactLoop` 类使用硬编码的简单 prompt，没有使用 `PromptManager`

**位置**: `agent/react.py:71-76`

```python
DEFAULT_SYSTEM_PROMPT = """You are an intelligent assistant that can use tools to help users.
When you need to use a tool, respond with a function call. When you have enough information
to answer the user's question, respond directly with your answer.
Available tools will be provided in the tools parameter. Use them when necessary."""
```

**建议**: 为 `ReactLoop` 增加动态 prompt 模板支持

---

### 1.2 模板缺失问题

**问题**: `LLMComponent` 调用 `get_prompt("doTasks")` 和 `get_prompt("historyTpl")`，但这两个模板在 `templates.txt` 中不存在

**位置**: `agent/components/llm.py:56,67`

**可能原因**: 可能还有其他 prompt 文件（如 `bot/prompts.txt`），没有统一管理

**建议**:
- 检查是否存在旧的 prompt 文件
- 将所有模板统一迁移到 `agent/prompts/templates.txt`
- 或者移除对不存在模板的引用

---

### 1.3 上下文构建方式不一致

**问题**: 存在两套并行的系统，使用不同的 prompt 格式

| 系统 | 位置 | 格式 |
|------|------|------|
| 新系统 | `agent/react.py` + `agent/core.py` | OpenAI Function Calling + 简单硬编码 prompt |
| 旧系统 | `agent/components/llm.py` | JSON 格式响应 + `doTasks`/`historyTpl` 模板 |

**建议**: 统一为新系统，逐步移除旧的 `LLMComponent`

---

### 1.4 缺少高级上下文工程特性

#### 1.4.1 对话摘要/压缩
- **问题**: 当前把所有历史消息传给 LLM，长对话会超 token 限制
- **影响**:
  - 超过 context window
  - "Lost in the middle" 问题（中间的信息被忽略）
  - Token 成本高

**建议实现**:
```python
class ContextCompressor:
    """上下文压缩器"""

    def compress_history(self, messages: List[Message]) -> List[Message]:
        """压缩对话历史"""
        # 1. 保留最近 N 条消息
        # 2. 早期消息生成摘要
        # 3. 保留重要消息（用户标记、工具调用失败等）
        pass
```

#### 1.4.2 Few-Shot 示例注入
- **问题**: 没有为复杂任务提供示例
- **建议**: 在 prompt 模板中增加示例部分

```
## Examples
Example 1:
User: "查看 nginx 日志中的错误"
Assistant: Uses exec_terminal_cmd with "tail -f /var/log/nginx/error.log"

Example 2:
User: "重启所有停止的 Docker 容器"
Assistant: Uses exec_terminal_cmd with "docker ps -a -q | xargs -r docker start"
```

#### 1.4.3 动态上下文选择（RAG 风格）
- **问题**: 所有历史都传入，没有相关性过滤
- **建议实现**:
  - 语义相似度检索相关历史对话
  - 滑动窗口 + 重要消息保留
  - 基于任务类型的上下文选择

```python
class ContextSelector:
    """动态上下文选择器"""

    def select_relevant_context(
        self,
        current_input: str,
        all_history: List[Message],
        max_tokens: int = 4000
    ) -> List[Message]:
        """选择相关的上下文"""
        # 1. 计算当前输入与历史消息的相似度
        # 2. 选择最相关的消息
        # 3. 确保 token 数量不超过限制
        pass
```

#### 1.4.4 Reflection/Thought 模板
- **问题**: 没有 CoT（Chain of Thought）结构化输出
- **建议**: 增加思考步骤的模板

```
## Thought Process
1. Understand the user's request
2. Identify what information is needed
3. Plan which tools to use
4. Execute and verify results
```

---

### 1.5 Prompt 模板改进建议

**当前 `react_default` 模板的不足**:
- 缺少终端操作的专项指导
- 缺少错误处理策略
- 缺少工具选择的示例

**建议增加**:
- `terminal_operations`: 终端操作专项 prompt
- `error_recovery`: 错误恢复策略 prompt
- `multi_step_planning`: 多步骤规划 prompt

---

## 二、产品规划

### 2.1 多标签页与多 Agent 支持

#### 功能描述
Agent 可以自动创建前端标签页，每个标签页对应一个独立的 Agent 实例执行任务。

#### 核心能力

1. **Agent 自动创建标签页**
   - Agent 识别到需要并行处理多个任务时
   - 自动请求创建新标签页
   - 新标签页 = 新 Agent 实例 = 新 PTY 实例

2. **标签页名称**
   - 默认名称: Agent 根据任务内容自动生成
   - 支持用户修改标签页名称
   - 名称用于预览当前标签页正在处理的任务

3. **标签页状态同步**
   - 显示当前状态: 运行中/等待用户输入/已完成
   - 显示最后一条消息摘要
   - 显示未读消息数量

#### 使用场景示例

```
用户: "帮我看一下三个服务器的日志：server1、server2、server3"

Agent 思考：这是三个独立的任务，可以并行处理

Agent 行动：
1. 创建标签页 "Server1 日志监控"
   - 新 Agent A → SSH 到 server1 → tail -f /var/log/app.log

2. 创建标签页 "Server2 日志监控"
   - 新 Agent B → SSH 到 server2 → tail -f /var/log/app.log

3. 创建标签页 "Server3 日志监控"
   - 新 Agent C → SSH 到 server3 → tail -f /var/log/app.log

用户可以：
- 切换标签页查看不同服务器的日志
- 重命名标签页为 "生产环境-Server1"
- 关闭不需要的标签页
```

#### 技术实现要点

1. **前端层面**
   - 标签页组件（类似浏览器标签页）
   - 标签页可拖拽排序
   - 标签页右键菜单（重命名、关闭、固定）

2. **后端层面**
   - Session 管理：1 标签页 = 1 Session ID = 1 Agent 实例
   - 消息路由：根据标签页 ID 路由消息到对应的 Agent
   - 状态同步：Agent 状态变化推送到前端标签页

3. **Agent 能力**
   - 新增 Tool: `create_tab(tab_name, task_description)`
   - Agent 调用此工具时，后端创建新 Session 并通知前端
   - 前端创建新标签页并建立 WebSocket 连接

#### 数据结构设计

```python
# 标签页信息
class TabInfo:
    tab_id: str                    # 唯一标识
    session_id: str                # 对应的 Session ID
    name: str                      # 标签页名称
    task_description: str          # 任务描述
    status: str                    # 状态: running/waiting/completed
    last_message: str              # 最后一条消息摘要
    unread_count: int              # 未读消息数
    created_at: datetime           # 创建时间
    is_pinned: bool                # 是否固定
```

#### API 设计

```python
# Agent 调用
@tool
def create_tab(name: str, task: str) -> dict:
    """
    创建一个新的标签页来执行独立任务

    Args:
        name: 标签页名称
        task: 任务描述

    Returns:
        {"tab_id": "xxx", "status": "created"}
    """

# WebSocket 事件
{
    "event": "tab_created",
    "data": {
        "tab_id": "tab_123",
        "name": "Server1 日志监控",
        "task": "SSH to server1 and monitor logs"
    }
}

{
    "event": "tab_renamed",
    "data": {
        "tab_id": "tab_123",
        "new_name": "生产环境-Server1"
    }
}
```

---

### 2.2 后续产品方向思考

1. **标签页间通信**
   - Agent A 可以向 Agent B 发送消息
   - 实现标签页间的协作

2. **标签页模板**
   - 保存常用的标签页配置
   - 一键创建多个监控标签页

3. **标签页组**
   - 相关标签页可以分组
   - 折叠/展开整个组

4. **任务历史与回放**
   - 标签页关闭后保留历史
   - 可以重新打开已关闭的标签页

---

## 三、优先级建议

| 优先级 | 任务 | 预计工作量 | 依赖 |
|--------|------|-----------|------|
| P0 | 统一 prompt 模板系统 | 0.5天 | 无 |
| P0 | 移除旧的 LLMComponent | 1天 | 统一模板后 |
| P1 | 实现对话历史压缩 | 2天 | 无 |
| P1 | 多标签页基础功能 | 3-4天 | 无 |
| P2 | 动态上下文选择 | 2-3天 | 向量检索 |
| P2 | Few-Shot 示例注入 | 1天 | 模板系统 |
| P3 | 标签页高级功能（模板、分组） | 2-3天 | 基础功能完成 |

---

## 四、相关文档

- 重构计划: `docs/REFACTOR_PLAN.md`
- Agent 核心设计: `docs/PHASE_2_AGENT_CORE.md`
- CLI 模式: `docs/CLI.md`
- Web 模式: `docs/WEB.md`
