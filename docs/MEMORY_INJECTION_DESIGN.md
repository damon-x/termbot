# 记忆注入方案设计

## 问题分析

是否在处理用户消息时自动注入长期记忆？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **全部注入** | LLM 能看到所有历史 | Token 浪费，干扰判断，窗口限制 |
| **手动工具** | 不污染上下文 | LLM 可能错过相关记忆 |
| **智能 RAG** ✅ | 按需注入，精准高效 | 需要检索机制 |

## 推荐方案：智能 RAG

### 核心思想
- **不是每次都注入所有记忆**
- 而是检索与用户消息相关的记忆片段
- 只在相关时注入检索结果

### 实现方式

#### 方案 A：系统提示词注入（推荐）
```python
# 在 ReactLoop.run() 开始时
def _build_messages(self, user_input: str) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": self.system_prompt}]

    # 检索相关记忆
    relevant_memories = self._retrieve_relevant_memory(user_input)

    if relevant_memories:
        # 注入到系统消息，不影响对话历史
        memory_context = self._format_memory_context(relevant_memories)
        messages[0]["content"] += f"\n\n[Relevant Context]\n{memory_context}"

    messages.extend(self.context.get_messages())
    return messages
```

#### 方案 B：用户消息增强
```python
# 在添加用户消息前增强
def run(self, user_input: str) -> ReactResult:
    # 检索相关记忆
    relevant_memories = self._retrieve_relevant_memory(user_input)

    if relevant_memories:
        enhanced_input = self._format_memory_enhancement(user_input, relevant_memories)
    else:
        enhanced_input = user_input

    self.context.add_message("user", enhanced_input)
    ...
```

### 检索策略

```python
def _retrieve_relevant_memory(
    self,
    user_input: str,
    max_results: int = 3,
    min_similarity: float = 0.3
) -> List[str]:
    """检索与用户输入相关的记忆"""
    from agent.memory.tool import memory_tool

    # 使用现有的文本搜索
    search_results = memory_tool.search_memory(user_input)

    # 限制返回数量和相关性
    return search_results[:max_results] if search_results else []
```

### 控制参数

```python
# 配置注入行为
ENABLE_MEMORY_INJECTION = True    # 总开关
MAX_INJECT_MEMORIES = 3          # 最多注入几条
MIN_SIMILARITY_THRESHOLD = 0.3   # 相似度阈值
```

## 优点

1. **精准** - 只注入相关的记忆
2. **高效** - 不浪费 token
3. **非侵入** - 不污染对话历史
4. **可控** - 可配置注入策略

## 实现建议

### 轻量级版本（立即可做）
- 使用现有的 `memory_tool.search_memory()`
- 在 `ReactLoop._build_messages()` 中增强系统提示词
- 无需改动其他代码

### 增强版本（可选）
- 使用向量数据库（已有 `infrastructure/memory/vector.py`）
- 计算语义相似度，而不是关键词匹配
- 支持更复杂的检索策略

## 代码位置

需要修改的文件：
- `agent/react.py` - 添加 `_retrieve_relevant_memory()` 和 `_build_messages()`
- `agent/core.py` 或配置文件 - 添加记忆注入开关
